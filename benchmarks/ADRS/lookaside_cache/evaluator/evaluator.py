#!/usr/bin/env python3
"""P-native scorer for the look-aside cache benchmark.

This evaluator scores the full P implementation directly:
- no separate declarative design DSL
- real `p compile`
- fixed LSI-focused `p check` tests
- fixed client-facing read/write latency scenarios derived from the P code
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from statistics import fmean
from typing import Dict, List, Tuple

BUGS_FOUND_RE = re.compile(r"Found\s+(\d+)\s+bug(?:s)?\b", re.IGNORECASE)
REQUIRED_ARTIFACT_PATH = "PSrc/Machines.p"

PROFILE_STAGE1 = "stage1"
PROFILE_STAGE2 = "stage2"

LSI_TESTCASES = (
    "tcCandidateWarmThenWrite",
    "tcCandidateMultiClientConflict",
)

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_SEND_EVENT_RE = re.compile(r"\bsend\s+[^,;]+,\s*(e[A-Za-z0-9_]+)\b")

CANONICAL_DIRECT_READ_LATENCY = 5.3
CANONICAL_DIRECT_WRITE_LATENCY = 6.3

INTERNAL_SEND_COST = 0.8
CLIENT_REPLY_COST = 0.5
DB_READ_COST = 4.0
DB_WRITE_COST = 5.0
CACHE_HIT_LOCAL_COST = 0.25
CACHE_FILL_COST = 0.40
CACHE_UPDATE_COST = 0.45
CACHE_INVALIDATE_COST = 0.15
BACKGROUND_REFRESH_TAX = 0.40
BALANCED_SPEEDUP_TARGET = 1.10
SCORED_SYSTEM_CANDIDATES = ("DirectReadWriteSystem", "LookasideCacheSystem")


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_comments(text: str) -> str:
    no_block = _BLOCK_COMMENT_RE.sub("", text)
    return _LINE_COMMENT_RE.sub("", no_block)


def _extract_braced_block(text: str, brace_index: int) -> str | None:
    if brace_index < 0 or brace_index >= len(text) or text[brace_index] != "{":
        return None
    depth = 0
    for index in range(brace_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_index + 1 : index]
    return None


def _extract_named_block(text: str, kind: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(kind)}\s+{re.escape(name)}\b", text)
    if not match:
        return None
    brace_index = text.find("{", match.end())
    if brace_index < 0:
        return None
    return _extract_braced_block(text, brace_index)


def _extract_handler_body(machine_body: str | None, event_name: str) -> str:
    if not machine_body:
        return ""
    match = re.search(rf"\bon\s+{re.escape(event_name)}\s+do\b", machine_body)
    if not match:
        return ""
    brace_index = machine_body.find("{", match.end())
    if brace_index < 0:
        return ""
    return _extract_braced_block(machine_body, brace_index) or ""


def _extract_fun_bodies(machine_body: str | None) -> Dict[str, str]:
    if not machine_body:
        return {}
    funs: Dict[str, str] = {}
    for match in re.finditer(r"\bfun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", machine_body):
        name = match.group(1)
        brace_index = machine_body.find("{", match.end())
        if brace_index < 0:
            continue
        body = _extract_braced_block(machine_body, brace_index)
        if body is not None:
            funs[name] = body
    return funs


def _extract_guarded_branch(body: str, guard_pattern: str) -> str:
    match = re.search(guard_pattern, body)
    if not match:
        return ""
    brace_index = body.find("{", match.end())
    if brace_index < 0:
        return ""
    return _extract_braced_block(body, brace_index) or ""


def _extract_last_else_branch(body: str) -> str:
    matches = list(re.finditer(r"\belse\s*\{", body))
    if not matches:
        return ""
    brace_index = body.find("{", matches[-1].start())
    if brace_index < 0:
        return ""
    return _extract_braced_block(body, brace_index) or ""


def _count_sends_to_event(
    body: str,
    event_name: str,
    helpers: Dict[str, str],
    stack: tuple[str, ...] = (),
) -> int:
    count = len(re.findall(rf"\bsend\s+[^,;]+,\s*{re.escape(event_name)}\b", body))
    for helper_name, helper_body in helpers.items():
        if helper_name in stack:
            continue
        calls = len(re.findall(rf"\b{re.escape(helper_name)}\s*\(", body))
        if calls:
            count += calls * _count_sends_to_event(helper_body, event_name, helpers, stack + (helper_name,))
    return count


def _count_all_sends(body: str, helpers: Dict[str, str], stack: tuple[str, ...] = ()) -> int:
    count = len(_SEND_EVENT_RE.findall(body))
    for helper_name, helper_body in helpers.items():
        if helper_name in stack:
            continue
        calls = len(re.findall(rf"\b{re.escape(helper_name)}\s*\(", body))
        if calls:
            count += calls * _count_all_sends(helper_body, helpers, stack + (helper_name,))
    return count


def _count_local_cache_assignments(body: str) -> int:
    return len(re.findall(r"\blocalCache\s*\[[^\]]+\]\s*=", body))


def _count_local_cache_invalidations(body: str) -> int:
    return len(re.findall(r"\blocalCache\s*-\=\s*\(", body))


def _harmonic_mean(a: float, b: float) -> float:
    if a <= 0.0 or b <= 0.0:
        return 0.0
    return 2.0 * a * b / (a + b)


def _client_latency_score(impl_paths: List[Path], target_machine: str) -> Tuple[float, Dict[str, float]]:
    """Estimate client-perceived read/write latency on fixed benchmark scenarios."""
    full_text = "\n".join(_read_text(path) for path in impl_paths)
    code_text = _strip_comments(full_text)

    db_machine = _extract_named_block(code_text, "machine", "SimpleTiDB")
    direct_machine = _extract_named_block(code_text, "machine", "DirectReadWriteSystem")
    candidate_machine = _extract_named_block(code_text, "machine", target_machine)

    db_helpers = _extract_fun_bodies(db_machine)
    direct_helpers = _extract_fun_bodies(direct_machine)
    candidate_helpers = _extract_fun_bodies(candidate_machine)

    direct_read_body = _extract_handler_body(direct_machine, "eRead")
    direct_write_body = _extract_handler_body(direct_machine, "eWrite")
    db_read_body = _extract_handler_body(db_machine, "eRead")
    db_write_body = _extract_handler_body(db_machine, "eWrite")
    db_dbread_body = _extract_handler_body(db_machine, "eDbRead")
    candidate_read_body = _extract_handler_body(candidate_machine, "eRead")
    candidate_write_body = _extract_handler_body(candidate_machine, "eWrite")
    candidate_dbreadresp_body = _extract_handler_body(candidate_machine, "eDbReadResp")
    candidate_writeresp_body = _extract_handler_body(candidate_machine, "eWriteResp")

    direct_read_hops = max(1, _count_all_sends(direct_read_body, direct_helpers)) if direct_machine else 1
    direct_write_hops = max(1, _count_all_sends(direct_write_body, direct_helpers)) if direct_machine else 1
    db_read_reply_sends = max(1, _count_sends_to_event(db_read_body, "eReadResp", db_helpers))
    db_write_reply_sends = max(1, _count_sends_to_event(db_write_body, "eWriteResp", db_helpers))

    direct_read_latency = (
        direct_read_hops * INTERNAL_SEND_COST
        + DB_READ_COST
        + db_read_reply_sends * CLIENT_REPLY_COST
    )
    direct_write_latency = (
        direct_write_hops * INTERNAL_SEND_COST
        + DB_WRITE_COST
        + db_write_reply_sends * CLIENT_REPLY_COST
    )

    if target_machine == "DirectReadWriteSystem":
        read_speedup = CANONICAL_DIRECT_READ_LATENCY / max(direct_read_latency, 1e-9)
        write_speedup = CANONICAL_DIRECT_WRITE_LATENCY / max(direct_write_latency, 1e-9)
        balanced_speedup = _harmonic_mean(read_speedup, write_speedup)
        score = _clamp(balanced_speedup / BALANCED_SPEEDUP_TARGET)
        detail = {
            "estimated_direct_read_latency": float(direct_read_latency),
            "estimated_direct_write_latency": float(direct_write_latency),
            "estimated_candidate_read_hit_latency": float(direct_read_latency),
            "estimated_candidate_read_miss_latency": float(direct_read_latency),
            "estimated_candidate_write_latency": float(direct_write_latency),
            "estimated_avg_client_read_latency": float(direct_read_latency),
            "estimated_avg_client_write_latency": float(direct_write_latency),
            "read_speedup_vs_canonical_direct": float(read_speedup),
            "write_speedup_vs_canonical_direct": float(write_speedup),
            "balanced_client_speedup": float(balanced_speedup),
            "client_latency_balance_score": float(score),
            "write_invalidate_on_write": 0.0,
            "write_updates_cached_copy": 0.0,
            "write_allocates_cache": 0.0,
            "background_refresh_count": 0.0,
        }
        return score, detail

    hit_branch = _extract_guarded_branch(
        candidate_read_body,
        r"\bif\s*\(\s*req\.key\s+in\s+localCache\s*\)",
    )
    miss_branch = _extract_last_else_branch(candidate_read_body) or candidate_read_body

    hit_total_sends = _count_all_sends(hit_branch, candidate_helpers)
    hit_response_sends = _count_sends_to_event(hit_branch, "eReadResp", candidate_helpers)
    hit_internal_sends = max(0, hit_total_sends - hit_response_sends)
    read_hit_latency = (
        CACHE_HIT_LOCAL_COST
        + hit_internal_sends * INTERNAL_SEND_COST
        + max(1, hit_response_sends) * CLIENT_REPLY_COST
    )

    miss_outbound_db_reads = max(1, _count_sends_to_event(miss_branch, "eDbRead", candidate_helpers))
    db_read_return_sends = max(1, _count_sends_to_event(db_dbread_body, "eDbReadResp", db_helpers))
    miss_total_sends = _count_all_sends(candidate_dbreadresp_body, candidate_helpers)
    miss_client_responses = max(1, _count_sends_to_event(candidate_dbreadresp_body, "eReadResp", candidate_helpers))
    miss_refreshes = _count_sends_to_event(candidate_dbreadresp_body, "eDbRefresh", candidate_helpers)
    miss_internal_extra = max(0, miss_total_sends - miss_client_responses - miss_refreshes)
    cache_fills = min(1, _count_local_cache_assignments(candidate_dbreadresp_body))
    read_miss_latency = (
        miss_outbound_db_reads * INTERNAL_SEND_COST
        + DB_READ_COST
        + db_read_return_sends * INTERNAL_SEND_COST
        + miss_internal_extra * INTERNAL_SEND_COST
        + miss_client_responses * CLIENT_REPLY_COST
        + cache_fills * CACHE_FILL_COST
        + miss_refreshes * BACKGROUND_REFRESH_TAX
    )

    write_route_sends = max(1, _count_sends_to_event(candidate_write_body, "eWrite", candidate_helpers))
    write_invalidations = min(1, _count_local_cache_invalidations(candidate_write_body))
    write_updates = min(
        1,
        _count_local_cache_assignments(candidate_write_body) + _count_local_cache_assignments(candidate_writeresp_body),
    )
    write_reply_via_system = _count_sends_to_event(candidate_writeresp_body, "eWriteResp", candidate_helpers) > 0
    write_response_sends = max(1, _count_sends_to_event(db_write_body, "eWriteResp", db_helpers))
    write_ack_total_sends = _count_all_sends(candidate_writeresp_body, candidate_helpers)
    write_ack_client_responses = _count_sends_to_event(candidate_writeresp_body, "eWriteResp", candidate_helpers)
    write_ack_internal_extra = max(0, write_ack_total_sends - write_ack_client_responses)

    write_latency = write_route_sends * INTERNAL_SEND_COST + DB_WRITE_COST
    if write_reply_via_system:
        write_latency += write_response_sends * INTERNAL_SEND_COST
        write_latency += write_ack_internal_extra * INTERNAL_SEND_COST
        write_latency += max(1, write_ack_client_responses) * CLIENT_REPLY_COST
    else:
        write_latency += write_response_sends * CLIENT_REPLY_COST
    write_latency += write_invalidations * CACHE_INVALIDATE_COST
    write_latency += write_updates * CACHE_UPDATE_COST

    guarded_write_update = bool(
        re.search(r"\bif\s*\(\s*(?:resp|req)\.key\s+in\s+localCache\s*\)", candidate_writeresp_body)
    )
    write_allocates_cache = write_updates > 0 and not guarded_write_update and write_invalidations == 0
    write_updates_if_cached = write_updates > 0 and guarded_write_update and write_invalidations == 0

    read_latencies: List[float] = []
    write_latencies: List[float] = []

    read_latencies.extend([direct_read_latency, direct_read_latency])
    write_latencies.append(direct_write_latency)

    def simulate_lookaside_sequence(ops: List[str]) -> None:
        cached = False
        nonlocal read_latencies, write_latencies
        for op in ops:
            if op == "read":
                if cached:
                    read_latencies.append(read_hit_latency)
                else:
                    read_latencies.append(read_miss_latency)
                    cached = True
            else:
                write_latencies.append(write_latency)
                if write_invalidations:
                    cached = False
                elif write_allocates_cache:
                    cached = True
                elif write_updates_if_cached and cached:
                    cached = True

    simulate_lookaside_sequence(["read", "write", "read"])
    simulate_lookaside_sequence(["read", "write", "read", "write", "read"])

    avg_read_latency = fmean(read_latencies)
    avg_write_latency = fmean(write_latencies)
    read_speedup = CANONICAL_DIRECT_READ_LATENCY / max(avg_read_latency, 1e-9)
    write_speedup = CANONICAL_DIRECT_WRITE_LATENCY / max(avg_write_latency, 1e-9)
    balanced_speedup = _harmonic_mean(read_speedup, write_speedup)
    score = _clamp(balanced_speedup / BALANCED_SPEEDUP_TARGET)

    detail = {
        "estimated_direct_read_latency": float(direct_read_latency),
        "estimated_direct_write_latency": float(direct_write_latency),
        "estimated_candidate_read_hit_latency": float(read_hit_latency),
        "estimated_candidate_read_miss_latency": float(read_miss_latency),
        "estimated_candidate_write_latency": float(write_latency),
        "estimated_avg_client_read_latency": float(avg_read_latency),
        "estimated_avg_client_write_latency": float(avg_write_latency),
        "read_speedup_vs_canonical_direct": float(read_speedup),
        "write_speedup_vs_canonical_direct": float(write_speedup),
        "balanced_client_speedup": float(balanced_speedup),
        "client_latency_balance_score": float(score),
        "write_invalidate_on_write": float(write_invalidations),
        "write_updates_cached_copy": float(1.0 if write_updates else 0.0),
        "write_allocates_cache": float(1.0 if write_allocates_cache else 0.0),
        "background_refresh_count": float(miss_refreshes),
    }
    return score, detail


def _write_pproj(root: Path) -> None:
    template = _read_text(_project_root() / "OwnershipSafety.pproj")
    impl = sorted(root.glob("PSrc/**/*.p"))
    lines = ["  <InputFiles>"]
    for path in impl:
        rel = "./" + path.relative_to(root).as_posix()
        lines.append(f"    <PFile>{rel}</PFile>")
    lines += [
        "    <PFile>./PSpec/Spec.p</PFile>",
        "    <PFile>./PTst/TestDriver.p</PFile>",
        "    <PFile>./PTst/TestScript.p</PFile>",
        "    <PFile>./PForeign/</PFile>",
        "  </InputFiles>",
    ]
    rewritten = re.sub(
        r"<InputFiles>.*?</InputFiles>",
        "\n".join(lines),
        template,
        flags=re.DOTALL,
    )
    target = root / "OwnershipSafety.pproj"
    target.write_text(rewritten + ("" if rewritten.endswith("\n") else "\n"), encoding="utf-8")


def _write_generated_tests(root: Path, target_machine: str) -> None:
    driver = f"""// Generated fixed harness targeting {target_machine}.

machine CandidateWarmThenWriteDriver {{
    var db: machine;
    var system: machine;

    start state Init {{
        entry {{
            db = new SimpleTiDB();
            system = new {target_machine}((db = db, ));
            send system, eRead, (client = this, key = 40, podId = 0);
            goto AwaitWarmRead;
        }}
    }}

    state AwaitWarmRead {{
        on eReadResp do (resp: (key: int, value: int, podId: int)) {{
            send system, eWrite, (client = this, key = 40, value = 11, podId = 1);
            goto AwaitWrite;
        }}
    }}

    state AwaitWrite {{
        on eWriteResp do (resp: (key: int, success: bool, podId: int)) {{
            send system, eRead, (client = this, key = 40, podId = 2);
            goto AwaitSecondRead;
        }}
    }}

    state AwaitSecondRead {{
        on eReadResp do (resp: (key: int, value: int, podId: int)) {{
            goto Done;
        }}
    }}

    state Done {{
        ignore eReadResp, eWriteResp;
    }}
}}

machine CandidateMultiClientConflictDriver {{
    var db: machine;
    var system: machine;
    var step: int;

    start state Init {{
        entry {{
            db = new SimpleTiDB();
            system = new {target_machine}((db = db, ));
            step = 0;
            send system, eRead, (client = this, key = 41, podId = 0);
            goto Running;
        }}
    }}

    state Running {{
        on eReadResp do (resp: (key: int, value: int, podId: int)) {{
            if (step == 0) {{
                step = 1;
                send system, eWrite, (client = this, key = 41, value = 21, podId = 1);
                return;
            }}
            if (step == 2) {{
                step = 3;
                send system, eWrite, (client = this, key = 41, value = 22, podId = 3);
                return;
            }}
            if (step == 4) {{
                goto Done;
                return;
            }}
            goto Done;
        }}

        on eWriteResp do (resp: (key: int, success: bool, podId: int)) {{
            if (step == 1) {{
                step = 2;
                send system, eRead, (client = this, key = 41, podId = 2);
                return;
            }}
            if (step == 3) {{
                step = 4;
                send system, eRead, (client = this, key = 41, podId = 4);
                return;
            }}
            goto Done;
        }}
    }}

    state Done {{
        ignore eReadResp, eWriteResp;
    }}
}}
"""
    script = """test tcCandidateWarmThenWrite [main = CandidateWarmThenWriteDriver]:
    assert LSISafety in
    {CandidateWarmThenWriteDriver, SimpleTiDB, %s};

test tcCandidateMultiClientConflict [main = CandidateMultiClientConflictDriver]:
    assert LSISafety in
    {CandidateMultiClientConflictDriver, SimpleTiDB, %s};
""" % (target_machine, target_machine)
    (root / "PTst").mkdir(parents=True, exist_ok=True)
    (root / "PTst" / "TestDriver.p").write_text(driver, encoding="utf-8")
    (root / "PTst" / "TestScript.p").write_text(script, encoding="utf-8")


def _materialize_workspace(program_text: str, root: Path, target_machine: str) -> List[str]:
    notes: List[str] = []
    target = root / REQUIRED_ARTIFACT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(program_text, encoding="utf-8")

    repo = _project_root()
    (root / "PSpec").mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "PSpec" / "Spec.p", root / "PSpec" / "Spec.p", follow_symlinks=True)
    _write_generated_tests(root, target_machine)

    pf_repo = repo / "PForeign"
    pf_dst = root / "PForeign"
    if pf_dst.exists():
        shutil.rmtree(pf_dst)
    shutil.copytree(pf_repo, pf_dst)

    _write_pproj(root)
    return notes


def _list_psrc_files(root: Path) -> List[Path]:
    target = root / REQUIRED_ARTIFACT_PATH
    if not target.is_file():
        return []
    return [target]


def _find_checker_dll(out_root: Path, proj_name: str) -> Path | None:
    direct = out_root / "PChecker" / "net8.0" / f"{proj_name}.dll"
    if direct.is_file():
        return direct
    for dll in out_root.glob(f"PChecker/**/{proj_name}.dll"):
        if dll.is_file():
            return dll
    for dll in out_root.glob("PChecker/**/*.dll"):
        if dll.is_file():
            return dll
    return None


def _run_compile(workspace: Path, timeout: int) -> Tuple[bool, str]:
    out = workspace / "PGenerated"
    if out.exists():
        shutil.rmtree(out)
    proc = subprocess.run(
        ["p", "compile", "-pp", str(workspace / "OwnershipSafety.pproj"), "-o", str(out)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, log


def _parse_bug_count(output: str) -> int | None:
    best = None
    for match in BUGS_FOUND_RE.finditer(output):
        count = int(match.group(1))
        best = count if best is None else max(best, count)
    return best


def _run_lsi_case(
    dll: Path,
    testcase: str,
    schedules: int,
    timeout: int,
    workspace: Path,
) -> Tuple[bool, str, int | None]:
    proc = subprocess.run(
        [
            "p",
            "check",
            str(dll),
            "-tc",
            testcase,
            "-s",
            str(schedules),
            "-t",
            str(timeout),
        ],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout + 120,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    bugs = _parse_bug_count(output)
    if bugs is None:
        return False, output, None
    return bugs == 0 and proc.returncode == 0, output, bugs


def _compile_artifact_score(program_text: str, psrc_files: List[Path]) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if not psrc_files:
        notes.append(f"No implementation file found at `{REQUIRED_ARTIFACT_PATH}`.")
        return 0.0, notes
    if not program_text.strip():
        notes.append(f"`{REQUIRED_ARTIFACT_PATH}` is empty.")
        return 0.0, notes
    nonempty = [path for path in psrc_files if path.read_text(encoding="utf-8", errors="replace").strip()]
    if not nonempty:
        notes.append(f"`{REQUIRED_ARTIFACT_PATH}` is empty.")
        return 0.0, notes
    return 1.0, notes


def _combined_score(
    profile: str,
    compile_ok: float,
    latency: float,
    lsi_pass: bool,
    lsi_ran: bool,
) -> float:
    if profile == PROFILE_STAGE1:
        lsi_part = 1.0 if (lsi_pass and lsi_ran) else (0.15 if lsi_ran else 0.0)
        return _clamp(0.35 * compile_ok + 0.50 * latency + 0.15 * lsi_part)

    if not lsi_ran:
        return _clamp(0.10 * compile_ok + 0.10 * latency)
    if not lsi_pass:
        return _clamp(0.02 * compile_ok)
    return _clamp(0.25 * compile_ok + 0.50 * latency + 0.25 * 1.0)


def _evaluate_workspace(
    program_text: str,
    profile: str,
    compile_timeout: int,
    check_timeout: int,
    schedules: int,
    target_machine: str,
) -> Dict[str, object]:
    feedback_lines: List[str] = []
    metrics: Dict[str, float | str] = {"profile": profile, "scored_system_name": target_machine}

    with tempfile.TemporaryDirectory(prefix="lookaside_p_") as tmp:
        tmp_path = Path(tmp)
        materialize_notes = _materialize_workspace(program_text, tmp_path, target_machine)
        psrc_files = _list_psrc_files(tmp_path)

        struct_score, struct_notes = _compile_artifact_score(program_text, psrc_files)
        for note in materialize_notes + struct_notes:
            feedback_lines.append(f"- {note}")

        latency, latency_detail = _client_latency_score(psrc_files, target_machine)
        metrics.update({key: float(value) for key, value in latency_detail.items()})

        compile_ok = 0.0
        compile_log = ""
        if struct_score >= 1.0:
            ok, compile_log = _run_compile(tmp_path, compile_timeout)
            compile_ok = 1.0 if ok else 0.0
            if not ok:
                feedback_lines.append("p compile failed; syntax/compile score is 0.")
        else:
            feedback_lines.append("Generated source was empty or missing; skipping p compile.")

        metrics["compile_score"] = float(compile_ok * struct_score)
        metrics["syntax_structure_score"] = float(struct_score)
        effective_latency = latency if metrics["compile_score"] >= 1.0 else 0.0

        lsi_pass = False
        lsi_ran = False
        bugs_total = 0
        lsi_details: List[str] = []

        if compile_ok >= 1.0:
            dll = _find_checker_dll(tmp_path / "PGenerated", "OwnershipSafety")
            if dll is None:
                feedback_lines.append("Compile reported success but no checker DLL was found.")
            else:
                for testcase in LSI_TESTCASES:
                    lsi_ran = True
                    passed, _log, bugs = _run_lsi_case(dll, testcase, schedules, check_timeout, tmp_path)
                    if bugs is None:
                        lsi_pass = False
                        lsi_details.append(f"{testcase}: checker output unparsable")
                        feedback_lines.append(f"LSI check {testcase}: could not parse bug count; treating as failure.")
                        break
                    bugs_total += bugs
                    if not passed:
                        lsi_pass = False
                        lsi_details.append(f"{testcase}: found {bugs} bug(s)")
                        feedback_lines.append(f"LSI check {testcase}: found {bugs} bug(s).")
                        break
                    lsi_details.append(f"{testcase}: 0 bugs")
                else:
                    lsi_pass = True

        metrics["p_lsi_pass"] = 1.0 if lsi_pass else 0.0
        metrics["p_lsi_checks_ran"] = 1.0 if lsi_ran else 0.0
        metrics["p_lsi_bug_count"] = float(bugs_total)
        metrics["client_latency_balance_score"] = float(effective_latency)
        metrics["latency_proxy_score"] = float(effective_latency)

        combined = _combined_score(profile, metrics["compile_score"], effective_latency, lsi_pass, lsi_ran)
        metrics["combined_score"] = float(combined)

        feedback_lines.insert(
            0,
            "Scores (read together):\n"
            "  (1) LSI correctness — fixed PChecker Spec/tests; dominant in stage2.\n"
            "  (2) Client-perceived latency — fixed read/write scenarios estimate average client read latency and "
            "average client write latency, then reward balanced improvement.\n"
            f"  (3) Syntax / compile — non-empty generated `{REQUIRED_ARTIFACT_PATH}` plus successful `p compile`.\n",
        )
        feedback_lines.insert(1, f"Profile={profile} scored_system={target_machine} combined_score={combined:.4f}")
        feedback_lines.insert(
            2,
            f"  compile_score={metrics['compile_score']:.4f}  "
            f"client_latency_balance={effective_latency:.4f}  "
            f"lsi_pass={bool(lsi_pass)} (bugs_total={bugs_total})",
        )
        if profile == PROFILE_STAGE1:
            feedback_lines.insert(
                3,
                "  stage1: compile and client-latency balance dominate while LSI is reported more lightly.",
            )
        else:
            feedback_lines.insert(
                3,
                "  stage2: any LSI failure collapses the score near zero; passing LSI unlocks the full client-latency score.",
            )

        artifacts: Dict[str, str] = {"feedback": "\n".join(feedback_lines)}
        if compile_log.strip():
            artifacts["compile_log_tail"] = compile_log[-8000:]
        if lsi_details:
            artifacts["p_lsi_summary"] = "; ".join(lsi_details)

        result: Dict[str, object] = {
            "combined_score": float(combined),
            "runs_successfully": 1.0,
            "compile_score": float(metrics["compile_score"]),
            "syntax_structure_score": float(metrics["syntax_structure_score"]),
            "scored_system_name": target_machine,
            "client_latency_balance_score": float(effective_latency),
            "latency_proxy_score": float(effective_latency),
            "p_lsi_pass": float(metrics["p_lsi_pass"]),
            "p_lsi_checks_ran": float(metrics["p_lsi_checks_ran"]),
            "p_lsi_bug_count": float(metrics["p_lsi_bug_count"]),
            "metrics": metrics,
            "artifacts": artifacts,
        }
        result.update(artifacts)
        return result


def _evaluate_with_profile(program_path: str, profile: str) -> Dict[str, object]:
    compile_timeout = int(os.environ.get("P_SCORER_COMPILE_TIMEOUT", "240"))
    check_timeout = int(os.environ.get("P_SCORER_CHECK_TIMEOUT", "90"))
    schedules = int(os.environ.get("P_SCORER_LSI_SCHEDULES", "4" if profile == PROFILE_STAGE1 else "12"))

    try:
        program_text = _read_text(Path(program_path))
    except Exception as exc:
        return {
            "combined_score": 0.0,
            "runs_successfully": 0.0,
            "metrics": {"combined_score": 0.0, "evaluator_exception": 1.0, "profile": profile},
            "artifacts": {"error": f"{type(exc).__name__}: {exc}"},
            "error": f"{type(exc).__name__}: {exc}",
        }

    available_systems = [
        name
        for name in SCORED_SYSTEM_CANDIDATES
        if re.search(rf"\bmachine\s+{re.escape(name)}\b", program_text)
    ]
    if not available_systems:
        return {
            "combined_score": 0.0,
            "runs_successfully": 0.0,
            "metrics": {
                "combined_score": 0.0,
                "evaluator_exception": 1.0,
                "profile": profile,
            },
            "artifacts": {
                "error": "Program must define at least one scored system: DirectReadWriteSystem or LookasideCacheSystem."
            },
            "error": "Program must define at least one scored system: DirectReadWriteSystem or LookasideCacheSystem.",
        }

    try:
        all_results = [
            _evaluate_workspace(program_text, profile, compile_timeout, check_timeout, schedules, system_name)
            for system_name in available_systems
        ]
        best = max(all_results, key=lambda result: float(result.get("combined_score", 0.0)))
        if len(all_results) > 1:
            summary = "; ".join(
                f"{result.get('scored_system_name')}: {float(result.get('combined_score', 0.0)):.4f}"
                for result in all_results
            )
            best.setdefault("artifacts", {})
            assert isinstance(best["artifacts"], dict)
            best["artifacts"]["scored_system_candidates"] = summary
            best["scored_system_candidates"] = summary
            if isinstance(best.get("metrics"), dict):
                best["metrics"]["num_scored_system_candidates"] = float(len(all_results))
        return best
    except subprocess.TimeoutExpired as exc:
        return {
            "combined_score": 0.0,
            "runs_successfully": 0.0,
            "metrics": {"combined_score": 0.0, "evaluator_timeout": 1.0, "profile": profile},
            "artifacts": {"error": f"Subprocess timeout: {exc}"},
            "error": f"Subprocess timeout: {exc}",
        }
    except Exception as exc:
        return {
            "combined_score": 0.0,
            "runs_successfully": 0.0,
            "metrics": {"combined_score": 0.0, "evaluator_exception": 1.0, "profile": profile},
            "artifacts": {"error": f"{type(exc).__name__}: {exc}"},
            "error": f"{type(exc).__name__}: {exc}",
        }


def evaluate(program_path: str) -> Dict[str, object]:
    profile = os.environ.get("P_SCORER_PROFILE", PROFILE_STAGE2).strip().lower()
    if profile not in (PROFILE_STAGE1, PROFILE_STAGE2):
        profile = PROFILE_STAGE2
    return _evaluate_with_profile(program_path, profile)


def evaluate_stage1(program_path: str) -> Dict[str, object]:
    return _evaluate_with_profile(program_path, PROFILE_STAGE1)


if __name__ == "__main__":
    import sys

    print(json.dumps(evaluate(sys.argv[1]), indent=2))
