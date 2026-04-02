#!/usr/bin/env python3
"""Hidden evaluator runtime for the distributed cache protocol benchmark."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable


BENCH_ROOT = Path(__file__).resolve().parent / "hidden_benchmark"
PROJECT_NAME = "ProtocolDiscovery"
PROJECT_FILE = BENCH_ROOT / f"{PROJECT_NAME}.pproj"
CANDIDATE_FILE = Path("PSrc") / "Candidate.p"

SMOKE_CHECKS = {
    "tcTargetedLSI": 100,
    "tcBalancedLSI": 200,
    "tcWriteHeavyLSI": 200,
    "tcProxyDiscipline": 200,
}

FULL_CHECKS = {
    "tcTargetedLSI": 3000,
    "tcBalancedLSI": 4000,
    "tcWriteHeavyLSI": 4000,
    "tcProxyDiscipline": 3000,
}

VERBOSE_TESTCASE = "tcBalancedLSI"
VERBOSE_SCHEDULES = 20
VERBOSE_SEED = 7
SCH_PCT = 3
COMPILE_TIMEOUT = 180
CHECK_TIMEOUT = 900

REQUIRED_MACHINES = ("machine StorageProxy", "machine CacheNode")
FIXED_EVENTS = (
    "eClientRead",
    "eClientWrite",
    "eStorageRead",
    "eStorageWrite",
    "eStorageReadResp",
    "eStorageWriteResp",
    "eReadResp",
    "eWriteResp",
    "eMonitorProxyRequestIssued",
    "eMonitorProxyResponseDelivered",
    "eMonitorProxyEnqueue",
    "eMonitorProxyForward",
    "eMonitorProxyHold",
)


def _strip_evolve_markers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip() in {"# EVOLVE-BLOCK-START", "# EVOLVE-BLOCK-END"}:
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _normalize_candidate(program_path: str) -> str:
    candidate = _strip_evolve_markers(Path(program_path).read_text(encoding="utf-8"))
    missing = [name for name in REQUIRED_MACHINES if name not in candidate]
    if missing:
        raise ValueError(
            "Candidate must define both machine types. Missing: "
            + ", ".join(missing)
        )
    return candidate


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _count(pattern: str, text: str, flags: int = re.MULTILINE) -> int:
    return len(re.findall(pattern, text, flags))


def _has(pattern: str, text: str, flags: int = re.MULTILINE) -> float:
    return 1.0 if re.search(pattern, text, flags) else 0.0


def _static_design_metrics(candidate: str) -> tuple[Dict[str, float], list[str]]:
    notes: list[str] = []

    machine_score = 1.0 if all(name in candidate for name in REQUIRED_MACHINES) else 0.0
    queue_score = _has(r"seq\s*\[", candidate) * _has(r"\b(queue|q)\b", candidate)
    nondet_score = _has(r"\bchoose\s*\(", candidate) or _has(r"\$\s*\)", candidate) or _has(r"\bif\s*\(\$\)", candidate)
    proxy_step_score = _has(r"\beProxy(Tick|Step)\b", candidate) or _has(r"\bHandleStep\b", candidate)
    proxy_monitor_score = (
        _has(r"announce\s+eMonitorProxyRequestIssued\b", candidate)
        + _has(r"announce\s+eMonitorProxyResponseDelivered\b", candidate)
        + _has(r"announce\s+eMonitorProxyEnqueue\b", candidate)
        + _has(r"announce\s+eMonitorProxyForward\b", candidate)
        + _has(r"announce\s+eMonitorProxyHold\b", candidate)
    ) / 5.0
    routing_score = _has(r"send\s+\w+\s*,\s*eStorage(Read|Write)\b", candidate) * _has(
        r"send\s+\w+\s*,\s*e(ClientRead|ClientWrite|Proxy(Read|Write)|Storage(Read|Write))\b",
        candidate,
    )
    request_id_score = _clamp(
        (
            _has(r"\b(reqId|requestId|opId|nonce|token)\b", candidate)
            + _has(r"\b(reqId|requestId|opId|nonce|token)\s*:", candidate)
        )
        / 2.0
    )
    range_awareness_score = _clamp(
        (
            _has(r"\b(range|shard|tablet|ownership|epoch|lease)\b", candidate, flags=re.IGNORECASE)
            + _has(r"\btKeyRange\b", candidate)
        )
        / 2.0
    )
    scalability_signal_score = _clamp(0.55 * range_awareness_score + 0.45 * request_id_score)
    key_state_score = _clamp(
        (
            _has(r"map\s*\[\s*int\s*,", candidate)
            + _has(r"set\s*\[\s*int\s*\]", candidate)
            + _has(r"\b(lastVal|committed|pendingWrite|pendingWrites|lease|readLease|version|versions|kv)\b", candidate)
        )
        / 3.0
    )
    cache_signal = _has(r"fromCache\s*=\s*true", candidate) or _has(r"fromCache:\s*bool", candidate)

    fixed_redeclare_count = sum(
        _count(rf"^\s*event\s+{event}\b", candidate)
        for event in FIXED_EVENTS
    )
    forbidden_machine_count = _count(r"^\s*machine\s+(Database|StorageCluster)\b", candidate)
    complexity_penalty = 0.0
    line_count = len(candidate.splitlines())
    if line_count > 420:
        complexity_penalty = min(0.15, (line_count - 420) / 1800.0)

    idea_score = _clamp(
        0.16 * machine_score
        + 0.14 * queue_score
        + 0.12 * float(nondet_score)
        + 0.06 * float(proxy_step_score)
        + 0.18 * proxy_monitor_score
        + 0.08 * routing_score
        + 0.08 * key_state_score
        + 0.04 * float(cache_signal)
        + 0.06 * request_id_score
        + 0.08 * range_awareness_score
        - 0.20 * min(fixed_redeclare_count / 3.0, 1.0)
        - 0.08 * min(forbidden_machine_count, 1.0)
        - complexity_penalty
    )

    if fixed_redeclare_count > 0:
        notes.append("Candidate redeclares one or more fixed benchmark events.")
    if forbidden_machine_count > 0:
        notes.append("Candidate defines hidden-environment machines such as Database/StorageCluster.")
    if proxy_monitor_score < 1.0:
        notes.append("Proxy observability is incomplete: announce local<->proxy request/response and queue enqueue/forward/hold behavior.")
    if queue_score == 0.0 or not nondet_score:
        notes.append("Proxy queueing/nondeterministic forwarding structure is weak or missing.")
    if key_state_score < 0.34:
        notes.append("The design has little visible key-level safety state for stale-read prevention.")
    if request_id_score < 1.0:
        notes.append("Concurrent requests would be safer with explicit request/op identifiers for response matching.")
    if range_awareness_score < 1.0:
        notes.append("The design does not visibly account for sharding, tablet/range movement, or ownership changes.")

    metrics = {
        "idea_score": float(idea_score),
        "safety_score": float(idea_score),
        "combined_score": float(idea_score),
        "machine_interface_score": float(machine_score),
        "queue_structure_score": float(queue_score),
        "nondeterministic_proxy_score": float(bool(nondet_score)),
        "proxy_step_score": float(bool(proxy_step_score)),
        "proxy_monitor_score": float(proxy_monitor_score),
        "routing_signal_score": float(routing_score),
        "request_id_score": float(request_id_score),
        "range_awareness_score": float(range_awareness_score),
        "scalability_signal_score": float(scalability_signal_score),
        "key_state_score": float(key_state_score),
        "cache_signal_score": float(bool(cache_signal)),
        "fixed_event_redeclare_count": float(fixed_redeclare_count),
        "forbidden_machine_count": float(forbidden_machine_count),
        "line_count": float(line_count),
        "round_trip_efficiency": float(_clamp(0.35 + 0.30 * float(cache_signal) + 0.35 * key_state_score)),
        "cache_hit_rate": float(0.5 * float(cache_signal)),
        "compile_success": 0.0,
    }
    return metrics, notes


def _run_command(cmd: list[str], cwd: Path, timeout: int) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": " ".join(cmd),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(cmd),
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timeout": True,
        }


def _parse_summary(outdir: Path) -> Dict[str, str]:
    summary_files = sorted(outdir.rglob("*_pchecker_summary.txt"))
    if not summary_files:
        return {}

    parsed: Dict[str, str] = {}
    for line in summary_files[0].read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _make_workspace(candidate: str) -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="distributed_cache_eval_"))
    shutil.copytree(BENCH_ROOT, workspace, dirs_exist_ok=True)
    (workspace / CANDIDATE_FILE).write_text(candidate, encoding="utf-8")
    return workspace


def _compile_workspace(workspace: Path) -> Dict[str, Any]:
    result = _run_command(
        ["p", "compile", "-pp", PROJECT_FILE.name],
        cwd=workspace,
        timeout=COMPILE_TIMEOUT,
    )
    dll_path = workspace / "PGenerated" / "PChecker" / "net8.0" / f"{PROJECT_NAME}.dll"
    result["dll_path"] = dll_path
    result["passed"] = (not result["timeout"]) and result["returncode"] == 0 and dll_path.exists()
    return result


def _run_check(
    dll_path: Path,
    testcase: str,
    schedules: int,
    outdir: Path,
    verbose: bool = False,
) -> Dict[str, Any]:
    cmd = [
        "p",
        "check",
        str(dll_path),
        "-tc",
        testcase,
        "-s",
        str(schedules),
        "--sch-pct",
        str(SCH_PCT),
        "-o",
        str(outdir),
    ]
    if verbose:
        cmd.extend(["-v", "--seed", str(VERBOSE_SEED)])

    result = _run_command(cmd, cwd=dll_path.parent.parent.parent.parent, timeout=CHECK_TIMEOUT)
    summary = _parse_summary(outdir)
    bugs = int(summary.get("bugs", "1")) if summary else 1
    result["summary"] = summary
    result["bugs"] = bugs
    result["passed"] = (not result["timeout"]) and result["returncode"] == 0 and bugs == 0
    result["schedules"] = int(summary.get("schedules", schedules)) if summary else schedules
    return result


def _iter_trace_events(trace_dir: Path) -> Iterable[Dict[str, Any]]:
    for trace_path in sorted(trace_dir.rglob("*.trace.json")):
        data = json.loads(trace_path.read_text(encoding="utf-8"))
        for schedule in data:
            if not isinstance(schedule, list):
                continue
            for event in schedule:
                if isinstance(event, dict):
                    yield event


def _extract_efficiency_metrics(trace_dir: Path) -> Dict[str, float]:
    counts = {
        "client_reads": 0,
        "client_writes": 0,
        "cache_served_reads": 0,
        "proxy_requests": 0,
        "proxy_responses": 0,
        "storage_reads": 0,
        "storage_writes": 0,
        "proxy_enqueues": 0,
        "proxy_forwards": 0,
        "proxy_holds": 0,
    }

    pending_reads: Dict[int, bool] = {}

    for event in _iter_trace_events(trace_dir):
        if event.get("type") != "Announce":
            continue
        details = event.get("details", {})
        event_name = details.get("event")
        payload = details.get("payload", {}) or {}

        if event_name == "eMonitorClientReadIssued":
            counts["client_reads"] += 1
            pending_reads[int(payload["podId"])] = False
        elif event_name == "eMonitorClientWriteIssued":
            counts["client_writes"] += 1
        elif event_name == "eMonitorProxyRequestIssued":
            counts["proxy_requests"] += 1
        elif event_name == "eMonitorProxyResponseDelivered":
            counts["proxy_responses"] += 1
        elif event_name == "eMonitorStorageReadIssued":
            counts["storage_reads"] += 1
            pod_id = int(payload["podId"])
            if pod_id in pending_reads:
                pending_reads[pod_id] = True
        elif event_name == "eMonitorStorageWriteIssued":
            counts["storage_writes"] += 1
        elif event_name == "eMonitorProxyEnqueue":
            counts["proxy_enqueues"] += 1
        elif event_name == "eMonitorProxyForward":
            counts["proxy_forwards"] += 1
        elif event_name == "eMonitorProxyHold":
            counts["proxy_holds"] += 1
        elif event_name == "eMonitorReadCompleted":
            pod_id = int(payload["podId"])
            touched_storage = pending_reads.pop(pod_id, True)
            if not touched_storage:
                counts["cache_served_reads"] += 1

    client_ops = counts["client_reads"] + counts["client_writes"]
    local_proxy_round_trips = counts["proxy_requests"]
    local_proxy_round_trips_per_client_op = local_proxy_round_trips / max(client_ops, 1)
    storage_round_trips = counts["storage_reads"] + counts["storage_writes"]
    cache_hit_rate = counts["cache_served_reads"] / max(counts["client_reads"], 1)

    metrics = {
        **{key: float(value) for key, value in counts.items()},
        "client_ops": float(client_ops),
        "local_proxy_round_trips": float(local_proxy_round_trips),
        "local_proxy_round_trips_per_client_op": float(local_proxy_round_trips_per_client_op),
        "storage_round_trips": float(storage_round_trips),
        "round_trips_per_client_op": float(local_proxy_round_trips_per_client_op),
        "cache_hit_rate": float(cache_hit_rate),
        "round_trip_efficiency": float(1.0 / (1.0 + local_proxy_round_trips_per_client_op)),
        "proxy_hold_rate": float(
            counts["proxy_holds"] / max(counts["proxy_forwards"] + counts["proxy_holds"], 1)
        ),
    }
    return metrics


def _truncate(text: str, limit: int = 2000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... (truncated)"


def _format_check_feedback(title: str, checks: Dict[str, Dict[str, Any]]) -> str:
    lines = [title]
    for testcase, result in checks.items():
        status = "PASS" if result["passed"] else "FAIL"
        schedules = result.get("summary", {}).get("schedules", result.get("schedules", "?"))
        time_seconds = result.get("summary", {}).get("time_seconds", "?")
        lines.append(
            f"- {testcase}: {status} | schedules={schedules} | time_seconds={time_seconds}"
        )
    return "\n".join(lines)


def _format_static_feedback(metrics: Dict[str, float], notes: list[str]) -> str:
    lines = [
        "Static Idea Assessment",
        f"- idea_score={metrics['idea_score']:.4f}",
        f"- proxy_monitor_score={metrics['proxy_monitor_score']:.4f}",
        f"- queue_structure_score={metrics['queue_structure_score']:.4f}",
        f"- request_id_score={metrics['request_id_score']:.4f}",
        f"- range_awareness_score={metrics['range_awareness_score']:.4f}",
        f"- scalability_signal_score={metrics['scalability_signal_score']:.4f}",
        f"- key_state_score={metrics['key_state_score']:.4f}",
        f"- fixed_event_redeclare_count={metrics['fixed_event_redeclare_count']:.0f}",
    ]
    for note in notes:
        lines.append(f"- {note}")
    return "\n".join(lines)


def _evaluate_impl(program_path: str, full: bool) -> Dict[str, Any]:
    try:
        candidate = _normalize_candidate(program_path)
    except Exception as exc:
        return {
            "compile_success": 0.0,
            "combined_score": 0.0,
            "artifacts": {"feedback": f"Candidate normalization failed: {exc}"},
        }

    static_metrics, static_notes = _static_design_metrics(candidate)
    if not full:
        return {
            **static_metrics,
            "artifacts": {
                "feedback": _format_static_feedback(static_metrics, static_notes),
            },
        }

    workspace = _make_workspace(candidate)
    try:
        compile_result = _compile_workspace(workspace)
        if not compile_result["passed"]:
            soft_compile_score = _clamp(
                max(static_metrics["idea_score"] * 0.92, static_metrics["idea_score"] - 0.04)
            )
            return {
                **static_metrics,
                "compile_success": 0.0,
                "syntax_score": 0.0,
                "combined_score": float(soft_compile_score),
                "safety_score": float(_clamp(max(static_metrics["safety_score"] * 0.95, static_metrics["safety_score"] - 0.03))),
                "artifacts": {
                    "feedback": "\n".join(
                        part
                        for part in [
                            _format_static_feedback(static_metrics, static_notes),
                            "",
                            f"Stage 2 compile failed, but only a light penalty was applied: combined_score={soft_compile_score:.4f}",
                            "Compilation failed.",
                            _truncate(compile_result.get("stderr", "")),
                            _truncate(compile_result.get("stdout", "")),
                        ]
                        if part
                    )
                },
            }

        dll_path = compile_result["dll_path"]
        run_root = workspace / "eval_runs"
        run_root.mkdir(exist_ok=True)

        checks_to_run = FULL_CHECKS if full else SMOKE_CHECKS
        results: Dict[str, Dict[str, Any]] = {}
        for testcase, schedules in checks_to_run.items():
            outdir = run_root / testcase
            results[testcase] = _run_check(dll_path, testcase, schedules, outdir, verbose=False)

        pass_count = sum(1 for result in results.values() if result["passed"])
        safety_score = pass_count / max(len(results), 1)

        metrics: Dict[str, float] = {
            **static_metrics,
            "compile_success": 1.0,
            "syntax_score": 1.0,
            "modelcheck_safety_score": float(safety_score),
        }

        for testcase, result in results.items():
            metrics[f"{testcase.lower()}_safe"] = 1.0 if result["passed"] else 0.0

        verbose_outdir = run_root / "verbose"
        verbose_result = _run_check(
            dll_path,
            VERBOSE_TESTCASE,
            VERBOSE_SCHEDULES,
            verbose_outdir,
            verbose=True,
        )

        efficiency = _extract_efficiency_metrics(verbose_outdir if verbose_result["passed"] else run_root)
        metrics.update(efficiency)

        all_full_safe = pass_count == len(results)
        metrics["safety_score"] = _clamp(
            0.40 * static_metrics["idea_score"] + 0.60 * metrics["modelcheck_safety_score"]
        )
        metrics["combined_score"] = _clamp(
            0.35 * static_metrics["idea_score"]
            + 0.35 * metrics["modelcheck_safety_score"]
            + 0.20 * metrics["round_trip_efficiency"]
            + 0.10 * metrics["cache_hit_rate"]
        )
        if all_full_safe:
            metrics["combined_score"] = max(
                metrics["combined_score"],
                _clamp(0.78 + 0.15 * metrics["round_trip_efficiency"] + 0.07 * metrics["cache_hit_rate"]),
            )

        artifacts: Dict[str, Any] = {}
        artifacts["feedback"] = "\n".join(
            [
                _format_static_feedback(static_metrics, static_notes),
                "",
                _format_check_feedback("Full Checks", results),
                "",
                "Efficiency snapshot",
                f"- cache_hit_rate={metrics['cache_hit_rate']:.4f}",
                f"- local_proxy_round_trips_per_client_op={metrics['local_proxy_round_trips_per_client_op']:.4f}",
                f"- local_proxy_round_trips={metrics['local_proxy_round_trips']:.0f}",
                f"- proxy_requests={metrics['proxy_requests']:.0f}",
                f"- proxy_responses={metrics['proxy_responses']:.0f}",
                f"- storage_round_trips={metrics['storage_round_trips']:.0f}",
                f"- client_ops={metrics['client_ops']:.0f}",
                f"- proxy_enqueues={metrics['proxy_enqueues']:.0f}",
                f"- proxy_forwards={metrics['proxy_forwards']:.0f}",
                f"- proxy_holds={metrics['proxy_holds']:.0f}",
                "",
                f"- combined_score={metrics['combined_score']:.4f}",
                f"- safety_score={metrics['safety_score']:.4f}",
            ]
        )

        return {**metrics, "artifacts": artifacts}
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def evaluate_stage1(program_path: str) -> Dict[str, Any]:
    return _evaluate_impl(program_path, full=False)


def evaluate_stage2(program_path: str) -> Dict[str, Any]:
    return _evaluate_impl(program_path, full=True)


def evaluate(program_path: str) -> Dict[str, Any]:
    return _evaluate_impl(program_path, full=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a distributed-cache protocol candidate.")
    parser.add_argument("program_path")
    parser.add_argument(
        "--stage",
        choices=["stage1", "stage2", "full"],
        default="full",
    )
    args = parser.parse_args()

    if args.stage == "stage1":
        result = evaluate_stage1(args.program_path)
    elif args.stage == "stage2":
        result = evaluate_stage2(args.program_path)
    else:
        result = evaluate(args.program_path)

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
