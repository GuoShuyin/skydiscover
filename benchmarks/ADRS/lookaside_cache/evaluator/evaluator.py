import ast
import concurrent.futures
import json
import math
import os
import random
import re
import statistics
import time
import traceback
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple


CACHE_HIT_COST = 1.0
CACHE_MISS_PROBE_COST = 0.35
CACHE_FILL_COST = 0.75
CACHE_UPDATE_COST = 0.90
CACHE_INVALIDATE_COST = 0.30
DB_READ_COST = 8.0
DB_WRITE_COST = 10.0

assert CACHE_HIT_COST < DB_READ_COST
assert CACHE_MISS_PROBE_COST < DB_READ_COST
assert CACHE_FILL_COST < DB_READ_COST
assert CACHE_UPDATE_COST < DB_WRITE_COST
assert CACHE_INVALIDATE_COST < DB_WRITE_COST

DEVICE_SPEED_ANCHORS = [
    {
        "anchor": "metadata_plane",
        "read_cost": CACHE_MISS_PROBE_COST,
        "write_cost": CACHE_INVALIDATE_COST,
        "aliases": ["metadata_plane", "metadata", "meta", "index", "directory", "catalog", "router", "coordinator", "lease", "filter"],
        "description": "Control-plane or metadata-only logic that does not store full values.",
    },
    {
        "anchor": "staging_buffer",
        "read_cost": CACHE_FILL_COST,
        "write_cost": CACHE_UPDATE_COST,
        "aliases": ["staging_buffer", "staging", "buffer", "queue", "journal", "wal", "log", "ingress", "writeback", "write_back"],
        "description": "Short-lived staging or write-buffer tier for recent values.",
    },
    {
        "anchor": "cache",
        "read_cost": CACHE_HIT_COST,
        "write_cost": CACHE_UPDATE_COST,
        "aliases": ["cache", "memo", "hot", "warm", "edge", "l1", "l2", "l3"],
        "description": "Fast in-memory read-serving value tier.",
    },
    {
        "anchor": "replica",
        "read_cost": 2.5,
        "write_cost": 3.4,
        "aliases": ["replica", "mirror", "secondary", "follower", "shadow", "copy"],
        "description": "Read-serving value copy slower than cache but faster than the primary database.",
    },
    {
        "anchor": "remote_store",
        "read_cost": 5.25,
        "write_cost": 6.7,
        "aliases": ["remote_store", "remote", "blob", "object", "archive", "disk", "ssd", "tier", "spill", "backing"],
        "description": "Lower tier store that is still faster than the authoritative database.",
    },
    {
        "anchor": "authoritative_db",
        "read_cost": DB_READ_COST,
        "write_cost": DB_WRITE_COST,
        "aliases": ["authoritative_db", "db", "database", "primary", "authority", "authoritative", "source", "truth", "origin"],
        "description": "Primary source of truth.",
    },
]
DEVICE_SPEED_ANCHOR_MAP = {anchor["anchor"]: anchor for anchor in DEVICE_SPEED_ANCHORS}
DEVICE_SPEED_ANCHOR_INDEX = {anchor["anchor"]: index for index, anchor in enumerate(DEVICE_SPEED_ANCHORS)}
NON_AUTHORITATIVE_ANCHORS = [anchor for anchor in DEVICE_SPEED_ANCHORS if anchor["anchor"] != "authoritative_db"]
DEFAULT_PARAM_VALUES = {
    "scan_window": 16,
    "hot_read_threshold": 2,
    "hot_write_threshold": 2,
    "promote_target": "",
    "promote_min_reads": 2,
    "promote_min_writes": 0,
    "promote_max_scan_ratio": 0.85,
    "write_stage_target": "",
    "write_stage_min_writes": 2,
    "write_stage_max_scan_ratio": 0.95,
    "write_update_targets": [],
    "write_update_if_cached": [],
    "write_update_min_score": 3,
    "write_update_max_scan_ratio": 0.85,
    "write_invalidate_on_scan": [],
    "write_invalidate_scan_cutoff": 0.90,
    "write_invalidate_cold_targets": [],
    "write_invalidate_cold_score": 2,
}
_DESIGN_BLOCK_RE = re.compile(r"DESIGN-START(.*?)DESIGN-END", re.DOTALL)
_DEVICE_RE = re.compile(
    r"\b(authoritative|device)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*?)\}",
    re.DOTALL,
)
_PARAM_RE = re.compile(r"\bparam\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?);", re.DOTALL)
_FIELD_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?);", re.DOTALL)
_INLINE_COMMENT_RE = re.compile(r"//.*?$", re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_AI_DEVICE_JUDGE_CACHE: Dict[str, dict] = {}
_OPENAI_CLIENT = None


@dataclass(frozen=True)
class Expression:
    text: str


@dataclass
class DeviceSpec:
    kind: str
    name: str
    role: str
    raw_block: str
    doc: str
    stores_values: bool
    serves_reads: bool
    requested_capacity: Any
    requested_capacity_expr: str
    pricing: Dict[str, Any] = field(default_factory=dict)
    allocated_capacity: int = 0


@dataclass
class DesignSpec:
    authoritative: DeviceSpec
    devices: Dict[str, DeviceSpec]
    params: Dict[str, Any]
    raw_design: str


@dataclass
class RuntimeDevice:
    spec: DeviceSpec
    read_cost: float
    write_cost: float
    probe_cost: float
    invalidate_cost: float
    capacity: Optional[int]
    store: "OrderedDict[int, int]" = field(default_factory=OrderedDict)
    hits: int = 0
    misses: int = 0
    writes: int = 0
    invalidations: int = 0


class RollingTelemetry:
    def __init__(self, window_size: int) -> None:
        self.window_size = max(1, int(window_size))
        self.ops: Deque[Tuple[str, int]] = deque()
        self.reads: Counter = Counter()
        self.writes: Counter = Counter()
        self.keys: Counter = Counter()

    def push(self, op: str, key: int) -> None:
        self.ops.append((op, key))
        self.keys[key] += 1
        if op == "read":
            self.reads[key] += 1
        else:
            self.writes[key] += 1
        while len(self.ops) > self.window_size:
            old_op, old_key = self.ops.popleft()
            self.keys[old_key] -= 1
            if self.keys[old_key] <= 0:
                self.keys.pop(old_key, None)
            if old_op == "read":
                self.reads[old_key] -= 1
                if self.reads[old_key] <= 0:
                    self.reads.pop(old_key, None)
            else:
                self.writes[old_key] -= 1
                if self.writes[old_key] <= 0:
                    self.writes.pop(old_key, None)

    def read_count(self, key: int) -> int:
        return int(self.reads.get(key, 0))

    def write_count(self, key: int) -> int:
        return int(self.writes.get(key, 0))

    def hot_score(self, key: int) -> int:
        return self.read_count(key) + (2 * self.write_count(key))

    def scan_ratio(self) -> float:
        if not self.ops:
            return 0.0
        return len(self.keys) / float(len(self.ops))


def _get_openai_client():
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is None:
        from openai import OpenAI

        _OPENAI_CLIENT = OpenAI()
    return _OPENAI_CLIENT


def _strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT_RE.sub("", text)
    return _INLINE_COMMENT_RE.sub("", text)


def _extract_design_block(program_text: str) -> str:
    match = _DESIGN_BLOCK_RE.search(program_text)
    if match is None:
        raise ValueError("Program must contain a DESIGN-START / DESIGN-END block.")
    return match.group(1)


def _split_top_level(text: str) -> List[str]:
    items: List[str] = []
    current: List[str] = []
    depth = 0
    in_string = False
    escape = False
    quote = ""
    for char in text:
        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            in_string = True
            quote = char
            current.append(char)
            continue
        if char in "([{" :
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _parse_json_like_object(content: str) -> Optional[dict]:
    content = content.strip()
    if not content:
        return None
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(content[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _normalize_chat_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content or "")


def _safe_eval_numeric(expr: str, cache_capacity: int) -> float:
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id == "cache_capacity":
                return float(cache_capacity)
            if node.id == "INF":
                return float("inf")
            raise ValueError(f"Unknown symbol in expression: {node.id}")
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise ValueError(f"Unsupported arithmetic operator: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp):
            value = _eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"min", "max"}:
            args = [_eval(arg) for arg in node.args]
            if not args:
                raise ValueError("min/max require at least one argument")
            return float(min(args) if node.func.id == "min" else max(args))
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return float(_eval(tree))


def _parse_value(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return ""
    if value[0] in {'"', "'"} and value[-1] == value[0]:
        return ast.literal_eval(value)
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(part) for part in _split_top_level(inner)]
    if _IDENT_RE.match(value):
        return value
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return Expression(value)


def _parse_device_fields(body: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for field_name, raw_value in _FIELD_RE.findall(body):
        fields[field_name] = _parse_value(raw_value)
    return fields


def _default_stores_values(kind: str, role: str) -> bool:
    if kind == "authoritative":
        return True
    return role != "metadata_plane"


def _default_serves_reads(kind: str, role: str, stores_values: bool) -> bool:
    if kind == "authoritative":
        return True
    if not stores_values:
        return False
    return role in {"staging_buffer", "cache", "replica", "remote_store"}


def parse_design(program_text: str) -> DesignSpec:
    design_text = _extract_design_block(program_text)
    clean_text = _strip_comments(design_text)
    authoritative_specs: List[DeviceSpec] = []
    device_specs: Dict[str, DeviceSpec] = {}

    for kind, name, role, body in _DEVICE_RE.findall(clean_text):
        raw_fields = {field_name: raw_value.strip() for field_name, raw_value in _FIELD_RE.findall(body)}
        fields = _parse_device_fields(body)
        doc = str(fields.get("doc", "") or "").strip()
        stores_values = bool(fields.get("stores_values", _default_stores_values(kind, role)))
        serves_reads = bool(fields.get("serves_reads", _default_serves_reads(kind, role, stores_values)))
        requested_capacity = fields.get("capacity", "INF" if kind == "authoritative" else Expression("cache_capacity"))
        requested_capacity_expr = raw_fields.get("capacity", "INF" if kind == "authoritative" else "cache_capacity")
        spec = DeviceSpec(
            kind=kind,
            name=name,
            role=role,
            raw_block=body.strip(),
            doc=doc,
            stores_values=stores_values,
            serves_reads=serves_reads,
            requested_capacity=requested_capacity,
            requested_capacity_expr=requested_capacity_expr,
        )
        if kind == "authoritative":
            authoritative_specs.append(spec)
        else:
            if name in device_specs:
                raise ValueError(f"Duplicate device name: {name}")
            device_specs[name] = spec

    if len(authoritative_specs) != 1:
        raise ValueError("Design must declare exactly one authoritative device.")
    authoritative = authoritative_specs[0]

    params: Dict[str, Any] = {}
    for name, raw_value in _PARAM_RE.findall(clean_text):
        params[name] = _parse_value(raw_value)

    spec = DesignSpec(
        authoritative=authoritative,
        devices=device_specs,
        params=params,
        raw_design=design_text.strip(),
    )
    _validate_design_structure(spec)
    return spec


def _validate_design_structure(spec: DesignSpec) -> None:
    if spec.authoritative.role != "authoritative_db":
        raise ValueError("The authoritative device must use role `authoritative_db`.")
    for device in [spec.authoritative, *spec.devices.values()]:
        if device.serves_reads and not device.stores_values:
            raise ValueError(
                f"Device `{device.name}` sets serves_reads=true but stores_values=false; "
                "value-serving devices must store full values."
            )
    for name in spec.devices:
        if name == spec.authoritative.name:
            raise ValueError("Non-authoritative device name conflicts with the authoritative device name.")


def _resolve_scalar(value: Any, cache_capacity: int) -> Any:
    if isinstance(value, Expression):
        return _safe_eval_numeric(value.text, cache_capacity)
    if isinstance(value, list):
        return [_resolve_scalar(item, cache_capacity) for item in value]
    return value


def _resolve_capacity(value: Any, cache_capacity: int) -> Optional[int]:
    resolved = _resolve_scalar(value, cache_capacity)
    if isinstance(resolved, str) and resolved == "INF":
        return None
    if isinstance(resolved, (int, float)):
        if not math.isfinite(float(resolved)):
            return max(1, int(cache_capacity)) if cache_capacity > 0 else 1
        return max(0, int(float(resolved)))
    return max(1, int(cache_capacity)) if cache_capacity > 0 else 1


def _cap_ratio(value: Any, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _cap_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _dedupe_keep_order(items: Sequence[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _resolve_name_list(value: Any, valid_names: Sequence[str]) -> List[str]:
    if not isinstance(value, list):
        return []
    valid = set(valid_names)
    names = [item for item in value if isinstance(item, str) and item in valid]
    return _dedupe_keep_order(names)


def _resolve_single_name(value: Any, valid_names: Sequence[str]) -> str:
    if isinstance(value, str) and value in set(valid_names):
        return value
    return ""


def _allocate_value_tier_capacity(specs: Sequence[DeviceSpec], cache_capacity: int) -> None:
    value_devices = [spec for spec in specs if spec.kind != "authoritative" and spec.stores_values]
    if not value_devices:
        return
    budget = max(0, int(cache_capacity))
    if budget == 0:
        for spec in value_devices:
            spec.allocated_capacity = 0
        return

    default_request = max(1, budget)
    requests: List[int] = []
    for spec in value_devices:
        requested = _resolve_capacity(spec.requested_capacity, cache_capacity)
        if requested is None or requested <= 0:
            requested = default_request
        requested = max(1, min(requested, budget * 4))
        requests.append(requested)

    total_requested = sum(requests)
    if total_requested <= 0:
        equal = max(1, budget // len(value_devices))
        for spec in value_devices:
            spec.allocated_capacity = equal
        return

    raw_allocations = [(budget * request) / float(total_requested) for request in requests]
    allocations = [int(value) for value in raw_allocations]
    remainder = budget - sum(allocations)
    ranked = sorted(
        range(len(raw_allocations)),
        key=lambda index: (raw_allocations[index] - allocations[index], requests[index], -index),
        reverse=True,
    )
    for index in ranked[:remainder]:
        allocations[index] += 1
    for spec, allocation in zip(value_devices, allocations):
        spec.allocated_capacity = allocation
    for spec in specs:
        if spec.kind == "authoritative":
            spec.allocated_capacity = -1
        elif not spec.stores_values:
            spec.allocated_capacity = 0


def _semantic_allowed_anchors(device: DeviceSpec) -> Tuple[int, int]:
    if device.kind == "authoritative":
        index = DEVICE_SPEED_ANCHOR_INDEX["authoritative_db"]
        return index, index
    if device.serves_reads:
        return DEVICE_SPEED_ANCHOR_INDEX["staging_buffer"], DEVICE_SPEED_ANCHOR_INDEX["remote_store"]
    if device.stores_values:
        return DEVICE_SPEED_ANCHOR_INDEX["staging_buffer"], DEVICE_SPEED_ANCHOR_INDEX["remote_store"]
    return DEVICE_SPEED_ANCHOR_INDEX["metadata_plane"], DEVICE_SPEED_ANCHOR_INDEX["staging_buffer"]


def _allowed_interval_pairs(device: DeviceSpec) -> List[Tuple[str, str]]:
    left_index, right_index = _semantic_allowed_anchors(device)
    pairs: List[Tuple[str, str]] = []
    for index in range(left_index, right_index):
        left = DEVICE_SPEED_ANCHORS[index]["anchor"]
        right = DEVICE_SPEED_ANCHORS[index + 1]["anchor"]
        if right == "authoritative_db" and device.kind != "authoritative":
            pairs.append((left, right))
        else:
            pairs.append((left, right))
    return pairs


def _role_exact_anchor(device: DeviceSpec) -> Optional[str]:
    role = device.role.lower()
    for anchor in DEVICE_SPEED_ANCHORS:
        if role == anchor["anchor"]:
            chosen = anchor["anchor"]
            break
        if role in anchor["aliases"]:
            chosen = anchor["anchor"]
            break
    else:
        return None

    min_index, max_index = _semantic_allowed_anchors(device)
    chosen_index = DEVICE_SPEED_ANCHOR_INDEX[chosen]
    if chosen == "authoritative_db" and device.kind != "authoritative":
        return None
    if chosen_index < min_index or chosen_index > max_index:
        return None
    return chosen


def _device_metadata(device: DeviceSpec) -> dict:
    return {
        "device_name": device.name,
        "role_name": device.role,
        "doc": device.doc,
        "stores_values": device.stores_values,
        "serves_reads": device.serves_reads,
        "requested_capacity_expr": device.requested_capacity_expr,
        "raw_block": device.raw_block,
    }


def _heuristic_interval_choice(device: DeviceSpec) -> Optional[dict]:
    pairs = _allowed_interval_pairs(device)
    if not pairs:
        return None
    text = " ".join(
        [
            device.role,
            device.name,
            device.doc,
            device.raw_block,
        ]
    ).lower().replace("_", " ")
    best_pair = pairs[0]
    best_score = -1
    for left_name, right_name in pairs:
        score = 0
        left_anchor = DEVICE_SPEED_ANCHOR_MAP[left_name]
        right_anchor = DEVICE_SPEED_ANCHOR_MAP[right_name]
        for alias in left_anchor["aliases"]:
            if alias in text:
                score += 2
        for alias in right_anchor["aliases"]:
            if alias in text:
                score += 3
        if score > best_score:
            best_score = score
            best_pair = (left_name, right_name)
    return {
        "left_anchor": best_pair[0],
        "right_anchor": best_pair[1],
        "source": "heuristic_interval",
        "reasoning": "Heuristic placement from role, doc, and device block text.",
    }


def _ai_interval_choice(device: DeviceSpec) -> Optional[dict]:
    if not os.environ.get("OPENAI_API_KEY"):
        return None

    signature = json.dumps(_device_metadata(device), sort_keys=True)
    if signature in _AI_DEVICE_JUDGE_CACHE:
        return _AI_DEVICE_JUDGE_CACHE[signature]

    allowed_pairs = _allowed_interval_pairs(device)
    if not allowed_pairs:
        return None

    ladder_text = "\n".join(
        f"- {anchor['anchor']}: read={anchor['read_cost']}, write={anchor['write_cost']}, meaning={anchor['description']}"
        for anchor in DEVICE_SPEED_ANCHORS
    )
    allowed_text = "\n".join(f"- {left} .. {right}" for left, right in allowed_pairs)
    system_prompt = (
        "You are judging where a new storage-system device belongs on a fixed speed ladder. "
        "Use semantics only. Ignore any numeric latency claims inside the text. "
        "Return only a compact JSON object."
    )
    user_prompt = f"""Anchor ladder from fastest to slowest:
{ladder_text}

Allowed adjacent intervals for this device:
{allowed_text}

Device metadata:
{json.dumps(_device_metadata(device), indent=2, sort_keys=True)}

Choose exactly one allowed adjacent interval. Return JSON with exactly:
{{
  "left_anchor": "<anchor name>",
  "right_anchor": "<anchor name>",
  "reasoning": "<one short sentence>"
}}
"""

    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=os.environ.get("LOOKASIDE_DEVICE_JUDGE_MODEL", "gpt-5"),
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=180,
        )
        content = _normalize_chat_content(response.choices[0].message.content)
        parsed = _parse_json_like_object(content)
        if not isinstance(parsed, dict):
            return None
        left_anchor = str(parsed.get("left_anchor", "")).strip()
        right_anchor = str(parsed.get("right_anchor", "")).strip()
        if (left_anchor, right_anchor) not in allowed_pairs:
            return None
        result = {
            "left_anchor": left_anchor,
            "right_anchor": right_anchor,
            "source": "ai_interval",
            "reasoning": str(parsed.get("reasoning", "")).strip() or "AI-chosen interval placement.",
        }
        _AI_DEVICE_JUDGE_CACHE[signature] = result
        return result
    except Exception:
        return None


def _pricing_from_anchor(anchor_name: str, source: str, reasoning: str) -> dict:
    anchor = DEVICE_SPEED_ANCHOR_MAP[anchor_name]
    return {
        "pricing_mode": "exact_anchor",
        "source": source,
        "reasoning": reasoning,
        "anchor": anchor_name,
        "read_cost": float(anchor["read_cost"]),
        "write_cost": float(anchor["write_cost"]),
    }


def _pricing_from_interval(left_name: str, right_name: str, source: str, reasoning: str) -> dict:
    left_anchor = DEVICE_SPEED_ANCHOR_MAP[left_name]
    right_anchor = DEVICE_SPEED_ANCHOR_MAP[right_name]
    return {
        "pricing_mode": "interval_midpoint",
        "source": source,
        "reasoning": reasoning,
        "left_anchor": left_name,
        "right_anchor": right_name,
        "read_cost": float((left_anchor["read_cost"] + right_anchor["read_cost"]) / 2.0),
        "write_cost": float((left_anchor["write_cost"] + right_anchor["write_cost"]) / 2.0),
    }


def _resolve_device_pricing(device: DeviceSpec) -> dict:
    if device.kind == "authoritative":
        return _pricing_from_anchor(
            "authoritative_db",
            source="authoritative_exact",
            reasoning="The authoritative device is always charged as the database.",
        )

    exact_anchor = _role_exact_anchor(device)
    if exact_anchor is not None:
        return _pricing_from_anchor(
            exact_anchor,
            source="exact_role",
            reasoning=f"Declared role `{device.role}` maps exactly to `{exact_anchor}`.",
        )

    ai_choice = _ai_interval_choice(device)
    if ai_choice is not None:
        return _pricing_from_interval(
            ai_choice["left_anchor"],
            ai_choice["right_anchor"],
            source=ai_choice["source"],
            reasoning=ai_choice["reasoning"],
        )

    heuristic = _heuristic_interval_choice(device)
    if heuristic is None:
        return _pricing_from_anchor(
            "cache",
            source="fallback_exact",
            reasoning="Fallback pricing used the cache anchor.",
        )
    return _pricing_from_interval(
        heuristic["left_anchor"],
        heuristic["right_anchor"],
        source=heuristic["source"],
        reasoning=heuristic["reasoning"],
    )


def _normalized_probe_cost(read_cost: float) -> float:
    return min(float(read_cost), CACHE_MISS_PROBE_COST + (0.10 * float(read_cost)))


def _normalized_invalidate_cost(write_cost: float) -> float:
    return min(float(write_cost), CACHE_INVALIDATE_COST + (0.08 * float(write_cost)))


def _write_runtime_device(device: RuntimeDevice, key: int, value: int) -> None:
    if not device.spec.stores_values or device.capacity == 0:
        return
    device.store[key] = value
    device.store.move_to_end(key)
    if device.capacity is None:
        return
    while len(device.store) > device.capacity:
        device.store.popitem(last=False)


def _resolve_runtime_devices(spec: DesignSpec, cache_capacity: int) -> Dict[str, RuntimeDevice]:
    all_specs = [spec.authoritative, *spec.devices.values()]
    _allocate_value_tier_capacity(all_specs, cache_capacity)
    runtime_devices: Dict[str, RuntimeDevice] = {}
    for device_spec in all_specs:
        pricing = _resolve_device_pricing(device_spec)
        device_spec.pricing = pricing
        capacity = None if device_spec.kind == "authoritative" else int(device_spec.allocated_capacity)
        runtime_devices[device_spec.name] = RuntimeDevice(
            spec=device_spec,
            read_cost=float(pricing["read_cost"]),
            write_cost=float(pricing["write_cost"]),
            probe_cost=_normalized_probe_cost(pricing["read_cost"]),
            invalidate_cost=_normalized_invalidate_cost(pricing["write_cost"]),
            capacity=capacity,
        )
    return runtime_devices


def _resolve_runtime_params(spec: DesignSpec, cache_capacity: int, runtime_devices: Dict[str, RuntimeDevice]) -> Dict[str, Any]:
    resolved = {name: _resolve_scalar(value, cache_capacity) for name, value in spec.params.items()}
    for name, value in DEFAULT_PARAM_VALUES.items():
        resolved.setdefault(name, value)

    valid_names = [device.name for device in spec.devices.values()]
    readable_names = [device.name for device in spec.devices.values() if device.serves_reads and device.stores_values]

    read_order = _resolve_name_list(resolved.get("read_order", []), readable_names)
    if not read_order:
        read_order = [device.name for device in spec.devices.values() if device.serves_reads and device.stores_values]
    read_order = [name for name in read_order if runtime_devices[name].capacity != 0]
    read_order.append(spec.authoritative.name)
    resolved["read_order"] = _dedupe_keep_order(read_order)

    resolved["scan_window"] = _cap_int(resolved.get("scan_window"), 16, 4, 256)
    resolved["hot_read_threshold"] = _cap_int(resolved.get("hot_read_threshold"), 2, 1, 32)
    resolved["hot_write_threshold"] = _cap_int(resolved.get("hot_write_threshold"), 2, 1, 32)
    resolved["promote_target"] = _resolve_single_name(resolved.get("promote_target"), valid_names)
    resolved["promote_min_reads"] = _cap_int(resolved.get("promote_min_reads"), 2, 0, 32)
    resolved["promote_min_writes"] = _cap_int(resolved.get("promote_min_writes"), 0, 0, 32)
    resolved["promote_max_scan_ratio"] = _cap_ratio(resolved.get("promote_max_scan_ratio"), 0.85)
    resolved["write_stage_target"] = _resolve_single_name(resolved.get("write_stage_target"), valid_names)
    resolved["write_stage_min_writes"] = _cap_int(resolved.get("write_stage_min_writes"), 2, 0, 32)
    resolved["write_stage_max_scan_ratio"] = _cap_ratio(resolved.get("write_stage_max_scan_ratio"), 0.95)
    resolved["write_update_targets"] = _resolve_name_list(resolved.get("write_update_targets"), valid_names)
    resolved["write_update_if_cached"] = _resolve_name_list(resolved.get("write_update_if_cached"), valid_names)
    resolved["write_update_min_score"] = _cap_int(resolved.get("write_update_min_score"), 3, 0, 64)
    resolved["write_update_max_scan_ratio"] = _cap_ratio(resolved.get("write_update_max_scan_ratio"), 0.85)
    resolved["write_invalidate_on_scan"] = _resolve_name_list(resolved.get("write_invalidate_on_scan"), valid_names)
    resolved["write_invalidate_scan_cutoff"] = _cap_ratio(resolved.get("write_invalidate_scan_cutoff"), 0.90)
    resolved["write_invalidate_cold_targets"] = _resolve_name_list(resolved.get("write_invalidate_cold_targets"), valid_names)
    resolved["write_invalidate_cold_score"] = _cap_int(resolved.get("write_invalidate_cold_score"), 2, 0, 64)

    for name in resolved["read_order"]:
        if name == spec.authoritative.name:
            continue
        device = runtime_devices[name]
        if not device.spec.serves_reads or not device.spec.stores_values:
            raise ValueError(f"Device `{name}` cannot appear in read_order because it does not serve value reads.")

    return resolved


def _design_summary(spec: DesignSpec, params: Dict[str, Any], runtime_devices: Dict[str, RuntimeDevice]) -> dict:
    return {
        "authoritative_device": spec.authoritative.name,
        "devices": {
            name: {
                "role": runtime.spec.role,
                "doc": runtime.spec.doc,
                "stores_values": runtime.spec.stores_values,
                "serves_reads": runtime.spec.serves_reads,
                "allocated_capacity": runtime.capacity,
                "read_cost": runtime.read_cost,
                "write_cost": runtime.write_cost,
                "pricing": runtime.spec.pricing,
            }
            for name, runtime in runtime_devices.items()
        },
        "params": params,
    }


def _make_read(key: int, pod_id: int) -> dict:
    return {"op": "read", "key": key, "pod_id": pod_id}


def _make_write(key: int, value: int, pod_id: int) -> dict:
    return {"op": "write", "key": key, "value": value, "pod_id": pod_id}


def _hot_read_heavy(seed: int, length: int, key_space: int, hot_keys: Sequence[int]) -> List[dict]:
    rng = random.Random(seed)
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    for step in range(length):
        pod_id = step % 4
        if step and step % 11 == 0:
            key = hot_keys[step % len(hot_keys)]
            next_value[key] += 1
            workload.append(_make_write(key, next_value[key], pod_id))
            continue
        key = hot_keys[rng.randrange(len(hot_keys))] if rng.random() < 0.82 else rng.randrange(key_space)
        workload.append(_make_read(key, pod_id))
    return workload


def _scan_then_reuse(seed: int, length: int, key_space: int, hot_keys: Sequence[int]) -> List[dict]:
    rng = random.Random(seed)
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    scan_width = max(24, key_space // 2)
    for step in range(length):
        pod_id = (step * 3) % 5
        phase = step % 40
        if phase < 24:
            key = (step + phase) % scan_width
            if phase % 8 == 0:
                next_value[key] += 1
                workload.append(_make_write(key, next_value[key], pod_id))
            else:
                workload.append(_make_read(key, pod_id))
        else:
            key = hot_keys[rng.randrange(len(hot_keys))]
            if phase % 9 == 0:
                next_value[key] += 1
                workload.append(_make_write(key, next_value[key], pod_id))
            else:
                workload.append(_make_read(key, pod_id))
    return workload


def _write_burst(seed: int, length: int, key_space: int, hot_keys: Sequence[int]) -> List[dict]:
    rng = random.Random(seed)
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    for step in range(length):
        pod_id = step % 3
        if step % 7 in {0, 1, 2}:
            key = hot_keys[rng.randrange(len(hot_keys))]
            next_value[key] += 1
            workload.append(_make_write(key, next_value[key], pod_id))
        else:
            key = hot_keys[rng.randrange(len(hot_keys))] if rng.random() < 0.7 else rng.randrange(key_space)
            workload.append(_make_read(key, pod_id))
    return workload


def _multi_client_conflict(seed: int, length: int, key_space: int, hot_keys: Sequence[int]) -> List[dict]:
    rng = random.Random(seed)
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    pods = [0, 1, 2, 3]
    for step in range(length):
        round_index = step % 8
        key = hot_keys[(step // 8) % len(hot_keys)]
        pod_id = pods[step % len(pods)]
        if round_index in {0, 4}:
            next_value[key] += 1
            workload.append(_make_write(key, next_value[key], pod_id))
        elif round_index in {1, 2, 5, 6}:
            workload.append(_make_read(key, pod_id))
        else:
            noisy_key = hot_keys[rng.randrange(len(hot_keys))] if rng.random() < 0.7 else rng.randrange(key_space)
            if rng.random() < 0.25:
                next_value[noisy_key] += 1
                workload.append(_make_write(noisy_key, next_value[noisy_key], pod_id))
            else:
                workload.append(_make_read(noisy_key, pod_id))
    return workload


def _shifting_hotset(seed: int, length: int, key_space: int) -> List[dict]:
    rng = random.Random(seed)
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    hot_groups = [list(range(0, 4)), list(range(8, 12)), list(range(16, 20))]
    phase_len = max(1, length // len(hot_groups))
    for step in range(length):
        pod_id = (step + 1) % 6
        hot_keys = hot_groups[min(len(hot_groups) - 1, step // phase_len)]
        if step % 13 == 0:
            key = hot_keys[step % len(hot_keys)]
            next_value[key] += 1
            workload.append(_make_write(key, next_value[key], pod_id))
        elif rng.random() < 0.8:
            workload.append(_make_read(hot_keys[rng.randrange(len(hot_keys))], pod_id))
        else:
            workload.append(_make_read(rng.randrange(key_space), pod_id))
    return workload


def _mixed_zipf(seed: int, length: int, key_space: int) -> List[dict]:
    rng = random.Random(seed)
    weights = [1.0 / (rank + 1) for rank in range(key_space)]
    keys = list(range(key_space))
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    for step in range(length):
        pod_id = (step * 2) % 7
        key = rng.choices(keys, weights=weights, k=1)[0]
        if step % 10 == 0:
            next_value[key] += 1
            workload.append(_make_write(key, next_value[key], pod_id))
        else:
            workload.append(_make_read(key, pod_id))
    return workload


def _cold_random(seed: int, length: int, key_space: int) -> List[dict]:
    rng = random.Random(seed)
    workload: List[dict] = []
    next_value = {key: key for key in range(key_space)}
    for step in range(length):
        pod_id = rng.randrange(4)
        key = rng.randrange(key_space)
        if rng.random() < 0.22:
            next_value[key] += 1
            workload.append(_make_write(key, next_value[key], pod_id))
        else:
            workload.append(_make_read(key, pod_id))
    return workload


def generate_scenarios() -> List[dict]:
    return [
        {
            "name": "multi_client_conflict",
            "cache_capacity": 6,
            "workload": _multi_client_conflict(seed=7, length=480, key_space=24, hot_keys=[0, 1, 2, 3]),
        },
        {
            "name": "hot_read_heavy",
            "cache_capacity": 8,
            "workload": _hot_read_heavy(seed=11, length=480, key_space=48, hot_keys=[1, 2, 3, 4]),
        },
        {
            "name": "scan_then_reuse",
            "cache_capacity": 10,
            "workload": _scan_then_reuse(seed=23, length=520, key_space=64, hot_keys=[5, 6, 7, 8]),
        },
        {
            "name": "write_burst",
            "cache_capacity": 8,
            "workload": _write_burst(seed=37, length=500, key_space=40, hot_keys=[0, 1, 2]),
        },
        {
            "name": "shifting_hotset",
            "cache_capacity": 10,
            "workload": _shifting_hotset(seed=41, length=540, key_space=32),
        },
        {
            "name": "mixed_zipf",
            "cache_capacity": 12,
            "workload": _mixed_zipf(seed=53, length=620, key_space=50),
        },
        {
            "name": "cold_random",
            "cache_capacity": 16,
            "workload": _cold_random(seed=67, length=420, key_space=128),
        },
    ]


def _simulate_direct_baseline(workload: Sequence[dict]) -> dict:
    db_store: Dict[int, int] = {}
    latency = 0.0
    observed_reads: List[int] = []
    for item in workload:
        key = item["key"]
        if item["op"] == "read":
            latency += DB_READ_COST
            observed_reads.append(db_store.get(key, 0))
        else:
            latency += DB_WRITE_COST
            db_store[key] = item["value"]
    return {"total_latency": latency, "observed_reads": observed_reads}


def _simulate_safe_cache_baseline(workload: Sequence[dict], cache_capacity: int) -> dict:
    db_store: Dict[int, int] = {}
    cache: "OrderedDict[int, int]" = OrderedDict()
    latency = 0.0
    observed_reads: List[int] = []
    for item in workload:
        key = item["key"]
        if item["op"] == "read":
            if key in cache:
                latency += CACHE_HIT_COST
                cache.move_to_end(key)
                value = cache[key]
            else:
                latency += CACHE_MISS_PROBE_COST + DB_READ_COST + CACHE_FILL_COST
                value = db_store.get(key, 0)
                cache[key] = value
                cache.move_to_end(key)
                while len(cache) > cache_capacity:
                    cache.popitem(last=False)
            observed_reads.append(value)
        else:
            latency += DB_WRITE_COST + CACHE_UPDATE_COST
            db_store[key] = item["value"]
            cache[key] = item["value"]
            cache.move_to_end(key)
            while len(cache) > cache_capacity:
                cache.popitem(last=False)
    return {"total_latency": latency, "observed_reads": observed_reads}


def simulate_design(spec: DesignSpec, workload: Sequence[dict], cache_capacity: int) -> dict:
    runtime_devices = _resolve_runtime_devices(spec, cache_capacity)
    params = _resolve_runtime_params(spec, cache_capacity, runtime_devices)
    telemetry = RollingTelemetry(params["scan_window"])
    authoritative_device = runtime_devices[spec.authoritative.name]
    authoritative_store = authoritative_device.store
    total_latency = 0.0
    total_reads = 0
    correct_reads = 0
    lsi_violations = 0
    observed_reads: List[int] = []
    lsi_violation_details: List[dict] = []

    for item in workload:
        key = int(item["key"])
        pod_id = int(item["pod_id"])
        scan_ratio = telemetry.scan_ratio()
        recent_reads = telemetry.read_count(key)
        recent_writes = telemetry.write_count(key)
        hot_score = telemetry.hot_score(key)

        if item["op"] == "read":
            total_reads += 1
            value = None
            served_from = ""
            for device_name in params["read_order"]:
                device = runtime_devices[device_name]
                if device.spec.kind == "authoritative":
                    total_latency += device.read_cost
                    value = authoritative_store.get(key, 0)
                    served_from = device_name
                    break
                if key in device.store:
                    total_latency += device.read_cost
                    device.hits += 1
                    device.store.move_to_end(key)
                    value = device.store[key]
                    served_from = device_name
                    break
                total_latency += device.probe_cost
                device.misses += 1

            if value is None:
                total_latency += authoritative_device.read_cost
                value = authoritative_store.get(key, 0)
                served_from = spec.authoritative.name

            promote_target = params["promote_target"]
            qualifies_hot = recent_reads >= params["hot_read_threshold"] or recent_writes >= params["hot_write_threshold"]
            if (
                promote_target
                and promote_target != served_from
                and recent_reads >= params["promote_min_reads"]
                and recent_writes >= params["promote_min_writes"]
                and qualifies_hot
                and scan_ratio <= params["promote_max_scan_ratio"]
            ):
                target_device = runtime_devices[promote_target]
                if target_device.capacity != 0 and target_device.spec.stores_values:
                    total_latency += target_device.write_cost
                    target_device.writes += 1
                    _write_runtime_device(target_device, key, value)

            observed_reads.append(value)
            authoritative_value = authoritative_store.get(key, 0)
            if value == authoritative_value:
                correct_reads += 1
            else:
                lsi_violations += 1
                lsi_violation_details.append(
                    {
                        "pod_id": pod_id,
                        "key": key,
                        "served_value": value,
                        "db_value": authoritative_value,
                        "served_from": served_from,
                    }
                )
            telemetry.push("read", key)
            continue

        value = int(item["value"])
        total_latency += authoritative_device.write_cost
        authoritative_device.writes += 1
        authoritative_store[key] = value

        projected_writes = recent_writes + 1
        projected_hot_score = recent_reads + (2 * projected_writes)

        update_targets = set()
        stage_target = params["write_stage_target"]
        if (
            stage_target
            and projected_writes >= params["write_stage_min_writes"]
            and scan_ratio <= params["write_stage_max_scan_ratio"]
        ):
            update_targets.add(stage_target)

        if (
            projected_hot_score >= params["write_update_min_score"]
            and scan_ratio <= params["write_update_max_scan_ratio"]
        ):
            update_targets.update(params["write_update_targets"])

        for name in params["write_update_if_cached"]:
            device = runtime_devices[name]
            if key in device.store:
                update_targets.add(name)

        invalidate_targets = set()
        if scan_ratio >= params["write_invalidate_scan_cutoff"]:
            invalidate_targets.update(params["write_invalidate_on_scan"])
        if projected_hot_score < params["write_invalidate_cold_score"]:
            invalidate_targets.update(params["write_invalidate_cold_targets"])
        invalidate_targets -= update_targets

        for name in sorted(invalidate_targets):
            device = runtime_devices[name]
            if key in device.store:
                total_latency += device.invalidate_cost
                device.invalidations += 1
                device.store.pop(key, None)

        for name in sorted(update_targets):
            device = runtime_devices[name]
            if device.capacity == 0 or not device.spec.stores_values:
                continue
            total_latency += device.write_cost
            device.writes += 1
            _write_runtime_device(device, key, value)

        telemetry.push("write", key)

    cache_reads = sum(runtime_devices[name].hits + runtime_devices[name].misses for name in runtime_devices if name != spec.authoritative.name)
    cache_hits = sum(runtime_devices[name].hits for name in runtime_devices if name != spec.authoritative.name)
    lsi_violation_rate = 0.0 if total_reads == 0 else lsi_violations / total_reads
    correctness_rate = 1.0 if total_reads == 0 else correct_reads / total_reads
    cache_hit_rate = 0.0 if cache_reads == 0 else cache_hits / float(cache_reads)

    return {
        "total_latency": total_latency,
        "correctness_rate": correctness_rate,
        "lsi_violations": lsi_violations,
        "lsi_violation_rate": lsi_violation_rate,
        "lsi_safety_score": 1.0 - lsi_violation_rate,
        "cache_hit_rate": cache_hit_rate,
        "observed_reads": observed_reads,
        "lsi_violation_details": lsi_violation_details,
        "design": _design_summary(spec, params, runtime_devices),
        "device_stats": {
            name: {
                "hits": device.hits,
                "misses": device.misses,
                "writes": device.writes,
                "invalidations": device.invalidations,
                "final_keys": list(device.store.keys())[:16],
            }
            for name, device in runtime_devices.items()
        },
    }


def run_with_timeout(func, args=(), kwargs=None, timeout_seconds=30):
    kwargs = kwargs or {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutError(f"Function timed out after {timeout_seconds} seconds") from exc


def _evaluate_scenario(spec: DesignSpec, scenario: dict) -> dict:
    start = time.perf_counter()
    candidate = simulate_design(spec, scenario["workload"], cache_capacity=scenario["cache_capacity"])
    parse_time_ms = (time.perf_counter() - start) * 1000.0
    direct = _simulate_direct_baseline(scenario["workload"])
    safe_cache = _simulate_safe_cache_baseline(scenario["workload"], scenario["cache_capacity"])
    candidate_latency = max(candidate["total_latency"], 1e-9)
    return {
        "name": scenario["name"],
        "candidate_latency": candidate["total_latency"],
        "direct_latency": direct["total_latency"],
        "safe_cache_latency": safe_cache["total_latency"],
        "speedup_vs_direct": direct["total_latency"] / candidate_latency,
        "correctness_rate": candidate["correctness_rate"],
        "lsi_violations": candidate["lsi_violations"],
        "lsi_violation_rate": candidate["lsi_violation_rate"],
        "cache_hit_rate": candidate["cache_hit_rate"],
        "planner_time_ms": parse_time_ms,
        "evaluation_mode": "p_design",
        "design": candidate["design"],
        "device_stats": candidate["device_stats"],
    }


def evaluate(program_path):
    try:
        with open(program_path, "r", encoding="utf-8") as handle:
            program_text = handle.read()
    except OSError as exc:
        return {
            "combined_score": 0.0,
            "runs_successfully": 0.0,
            "error": f"Failed to read program: {exc}",
        }

    try:
        parse_start = time.perf_counter()
        spec = run_with_timeout(parse_design, args=(program_text,), timeout_seconds=30)
        parse_time_ms = (time.perf_counter() - parse_start) * 1000.0
        scenarios = generate_scenarios()
        scenario_summaries = [_evaluate_scenario(spec, scenario) for scenario in scenarios]
        average_speedup = statistics.mean(item["speedup_vs_direct"] for item in scenario_summaries)
        average_correctness = statistics.mean(item["correctness_rate"] for item in scenario_summaries)
        average_lsi_violations = statistics.mean(item["lsi_violations"] for item in scenario_summaries)
        average_lsi_violation_rate = statistics.mean(item["lsi_violation_rate"] for item in scenario_summaries)
        average_planner_time = statistics.mean(item["planner_time_ms"] for item in scenario_summaries)

        correctness_penalty = average_correctness ** 10
        lsi_rate_penalty = max(0.0, 1.0 - average_lsi_violation_rate) ** 12
        lsi_count_penalty = 1.0 / (1.0 + average_lsi_violations)
        combined_score = average_speedup * correctness_penalty * lsi_rate_penalty * lsi_count_penalty

        return {
            "combined_score": combined_score,
            "runs_successfully": 1.0,
            "average_speedup": average_speedup,
            "average_correctness": average_correctness,
            "average_lsi_violations": average_lsi_violations,
            "average_lsi_violation_rate": average_lsi_violation_rate,
            "average_planner_time": average_planner_time,
            "parse_time_ms": parse_time_ms,
            "scenario_summaries": scenario_summaries,
        }
    except Exception as exc:
        return {
            "combined_score": 0.0,
            "runs_successfully": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "benchmarks/ADRS/lookaside_cache/initial_program.p"
    print(json.dumps(evaluate(target), indent=2, sort_keys=True))
