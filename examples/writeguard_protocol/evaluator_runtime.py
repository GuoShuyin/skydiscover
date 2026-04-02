#!/usr/bin/env python3
"""Evaluator for the local WriteGuard P project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
WRITEGUARD_ROOT = REPO_ROOT / "p_WriteGuard"
SOURCE_FILE = WRITEGUARD_ROOT / "PSrc" / "Machines.p"
SPEC_FILE = WRITEGUARD_ROOT / "PSpec" / "Spec.p"
TEST_DRIVER_FILE = WRITEGUARD_ROOT / "PTst" / "TestDriver.p"
PFOREIGN_DIR = WRITEGUARD_ROOT / "PForeign"

SOURCE_TEXT = SOURCE_FILE.read_text(encoding="utf-8")
SLICE_START = SOURCE_TEXT.index("machine NetworkProxy {")
FIXED_PREFIX = SOURCE_TEXT[:SLICE_START]

PROJECT_FILE = """<Project>
  <ProjectName>WriteGuard</ProjectName>
  <InputFiles>
    <PFile>./PSrc/Machines.p</PFile>
    <PFile>./PSpec/Spec.p</PFile>
    <PFile>./PTst/TestDriver.p</PFile>
    <PFile>./PTst/TestScript.p</PFile>
    <PFile>./PForeign/</PFile>
  </InputFiles>
  <OutputDir>./PGenerated</OutputDir>
</Project>
"""

TEST_SCRIPT = """// PTst/TestScript.p

test tcGeneralLSI [main = TestDriver]:
    assert LSISafety in
    {TestDriver, TiDB, NetworkProxy, CLINKPod, AutoSharder, Client};

test tcProxyLSI [main = ProxyLSIDriver]:
    assert LSISafety in
    {ProxyLSIDriver, TiDB, NetworkProxy, CLINKPod, AutoSharder, WriteHammerClient, ReadHammerClient};

test tcProxyNoStaleWrite [main = ProxyLSIDriver]:
    assert NoStaleWriteCommitted in
    {ProxyLSIDriver, TiDB, NetworkProxy, CLINKPod, AutoSharder, WriteHammerClient, ReadHammerClient};

test tcDelayWriteNoStaleWrite [main = DelayWriteFocusedDriver]:
    assert NoStaleWriteCommitted in
    {DelayWriteFocusedDriver, TiDB, NetworkProxy, CLINKPod, AutoSharder, WriteHammerClient};
"""

SMOKE_CHECKS = {
    "tcGeneralLSI": 100,
    "tcProxyLSI": 300,
    "tcProxyNoStaleWrite": 300,
    "tcDelayWriteNoStaleWrite": 300,
}

FULL_CHECKS = {
    "tcProxyLSI": 10000,
    "tcProxyNoStaleWrite": 3000,
    "tcDelayWriteNoStaleWrite": 3000,
}

VERBOSE_SCHEDULES = 20
VERBOSE_SEED = 7
SCH_PCT = 3
COMPILE_TIMEOUT = 180
CHECK_TIMEOUT = 900
USER_FACING_NAME_MAP = {
    "WriteGuard": "SystemModel",
    "CLINKPod": "CacheNode",
    "NetworkProxy": "StorageProxy",
    "TiDB": "StorageBackend",
    "AutoSharder": "OwnershipController",
    "SetGuard": "SyncOwnership",
    "guardId": "versionId",
    "sliceHandle": "ownershipEpoch",
    "Guard": "OwnershipRecord",
}

IDENTIFIER_ALIASES = {
    "StorageProxy": "NetworkProxy",
    "CacheNode": "CLINKPod",
    "tOwnershipRecord": "tGuardHandle",
    "tStorageWriteReq": "tDbWriteReq",
    "tAccessHandle": "tOpHandle",
    "tCachedValue": "tCacheEntry",
    "eStorageRead": "eDbRead",
    "eStorageWrite": "eDbWrite",
    "eSyncOwnership": "eSetGuard",
    "eStorageReadResp": "eDbReadResp",
    "eStorageWriteResp": "eDbWriteResp",
    "eSyncOwnershipDone": "eSetGuardDone",
    "eStorageRestart": "eTabletRestart",
    "eFetchShardLayout": "eGetSplitPoints",
    "eFetchShardLayoutResp": "eGetSplitPointsResp",
    "eStorageSplit": "eTabletSplit",
    "eMonitorFenceDecision": "eMonitorGuardDecision",
    "versionId": "guardId",
    "ownershipEpoch": "sliceHandle",
    "hasOwnershipRecord": "hasGuard",
    "ownershipRecord": "guard",
    "VersionMismatch": "WriteGuardMismatch",
}

CLIENT_READ_RE = re.compile(r"^(?:Client|ReadHammer) \d+: READ key=")
CLIENT_WRITE_RE = re.compile(r"^(?:Client|HammerClient) \d+: WRITE key=")


def _strip_evolve_markers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip() in {"# EVOLVE-BLOCK-START", "# EVOLVE-BLOCK-END"}:
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _sanitize_user_facing_text(text: str) -> str:
    sanitized = text
    for original, replacement in USER_FACING_NAME_MAP.items():
        sanitized = sanitized.replace(original, replacement)
    return sanitized


def _translate_candidate_identifiers(candidate: str) -> str:
    translated = candidate
    for generic, hidden in sorted(IDENTIFIER_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        translated = re.sub(rf"\b{re.escape(generic)}\b", hidden, translated)
    return translated


def _normalize_candidate(program_path: str) -> str:
    candidate = _strip_evolve_markers(Path(program_path).read_text(encoding="utf-8"))
    groups = {
        "machine StorageProxy": ("machine StorageProxy",),
        "machine CacheNode": ("machine CacheNode",),
    }
    missing = [canonical for canonical, aliases in groups.items() if not any(alias in candidate for alias in aliases)]
    if missing:
        missing_str = ", ".join(missing)
        raise ValueError(
            f"Candidate must define both mutable machines. Missing: {missing_str}"
        )
    return _translate_candidate_identifiers(candidate)


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
    summary_path = outdir / "BugFinding" / "WriteGuard_pchecker_summary.txt"
    if not summary_path.exists():
        return {}

    parsed: Dict[str, str] = {}
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _make_workspace(candidate: str) -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="writeguard_eval_"))
    (workspace / "PSrc").mkdir()
    (workspace / "PSpec").mkdir()
    (workspace / "PTst").mkdir()

    (workspace / "PSrc" / "Machines.p").write_text(
        FIXED_PREFIX + candidate,
        encoding="utf-8",
    )
    shutil.copy2(SPEC_FILE, workspace / "PSpec" / "Spec.p")
    shutil.copy2(TEST_DRIVER_FILE, workspace / "PTst" / "TestDriver.p")
    (workspace / "PTst" / "TestScript.p").write_text(TEST_SCRIPT, encoding="utf-8")
    _copy_tree(PFOREIGN_DIR, workspace / "PForeign")
    (workspace / "WriteGuard.pproj").write_text(PROJECT_FILE, encoding="utf-8")

    return workspace


def _compile_workspace(workspace: Path) -> Dict[str, Any]:
    result = _run_command(
        ["p", "compile", "-pp", "WriteGuard.pproj"],
        cwd=workspace,
        timeout=COMPILE_TIMEOUT,
    )
    dll_path = workspace / "PGenerated" / "PChecker" / "net8.0" / "WriteGuard.dll"
    result["dll_path"] = dll_path
    result["passed"] = (not result["timeout"]) and result["returncode"] == 0 and dll_path.exists()
    return result


def _run_check(dll_path: Path, testcase: str, schedules: int, outdir: Path, verbose: bool = False) -> Dict[str, Any]:
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


def _iter_trace_logs(trace_dir: Path) -> Iterable[str]:
    for trace_path in sorted(trace_dir.rglob("*_verbose.trace.json")):
        data = json.loads(trace_path.read_text(encoding="utf-8"))
        for schedule in data:
            if not isinstance(schedule, list):
                continue
            for event in schedule:
                if not isinstance(event, dict):
                    continue
                if event.get("type") != "Print":
                    continue
                details = event.get("details", {})
                log = details.get("log")
                if isinstance(log, str):
                    yield log


def _extract_efficiency_metrics(trace_dir: Path) -> Dict[str, float]:
    counts = {
        "client_reads": 0,
        "client_writes": 0,
        "cache_hits": 0,
        "db_reads": 0,
        "db_writes": 0,
        "accepted_writes": 0,
        "rejected_writes": 0,
        "get_split_points": 0,
        "set_guard_attempts": 0,
        "ownership_transfers": 0,
        "proxy_delays": 0,
        "proxy_releases": 0,
    }

    for log in _iter_trace_logs(trace_dir):
        if CLIENT_READ_RE.match(log):
            counts["client_reads"] += 1
        elif CLIENT_WRITE_RE.match(log):
            counts["client_writes"] += 1

        if "CACHE HIT key=" in log:
            counts["cache_hits"] += 1
        if log.startswith("TiDB: Read key="):
            counts["db_reads"] += 1
        if log.startswith("TiDB: Write ACCEPTED"):
            counts["db_writes"] += 1
            counts["accepted_writes"] += 1
        if log.startswith("TiDB: Write REJECTED"):
            counts["db_writes"] += 1
            counts["rejected_writes"] += 1
        if log.startswith("TiDB: GetSplitPoints "):
            counts["get_split_points"] += 1
        if log.startswith("TiDB: SetGuard "):
            counts["set_guard_attempts"] += 1
        if "transfer to pod" in log or "ownership transfer to pod" in log:
            counts["ownership_transfers"] += 1
        if log.startswith("Proxy: delaying WRITE"):
            counts["proxy_delays"] += 1
        if log.startswith("Proxy: releasing delayed WRITE"):
            counts["proxy_releases"] += 1

    client_ops = counts["client_reads"] + counts["client_writes"]
    db_rpcs = counts["db_reads"] + counts["db_writes"]
    control_rpcs = counts["get_split_points"] + counts["set_guard_attempts"]
    total_rpcs = db_rpcs + control_rpcs

    rpc_per_client_op = total_rpcs / max(client_ops, 1)
    control_rpcs_per_transfer = control_rpcs / max(counts["ownership_transfers"], 1)
    cache_hit_rate = counts["cache_hits"] / max(counts["client_reads"], 1)

    metrics = {
        **{key: float(value) for key, value in counts.items()},
        "client_ops": float(client_ops),
        "db_rpcs": float(db_rpcs),
        "control_rpcs": float(control_rpcs),
        "total_rpcs": float(total_rpcs),
        "rpc_per_client_op": float(rpc_per_client_op),
        "control_rpcs_per_transfer": float(control_rpcs_per_transfer),
        "cache_hit_rate": float(cache_hit_rate),
        "rpc_efficiency": float(1.0 / (1.0 + rpc_per_client_op)),
        "transfer_efficiency": float(1.0 / (1.0 + control_rpcs_per_transfer)),
    }
    return metrics


def _truncate(text: str, limit: int = 2000) -> str:
    text = _sanitize_user_facing_text(text.strip())
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


def _artifact_feedback_key(title: str) -> str:
    return title.lower().replace(" ", "_") + "_feedback"


def _safety_artifacts(
    compile_result: Dict[str, Any],
    checks: Dict[str, Dict[str, Any]],
    title: str,
) -> Dict[str, Any]:
    artifacts: Dict[str, Any] = {}
    if checks:
        artifacts[_artifact_feedback_key(title)] = _format_check_feedback(title, checks)
    return artifacts


def _evaluate_impl(program_path: str, full: bool) -> Dict[str, Any]:
    try:
        candidate = _normalize_candidate(program_path)
    except Exception as exc:
        return {
            "compile_success": 0.0,
            "combined_score": 0.0,
            "artifacts": {"feedback": f"Candidate normalization failed: {exc}"},
        }

    workspace = _make_workspace(candidate)
    try:
        compile_result = _compile_workspace(workspace)
        if not compile_result["passed"]:
            return {
                "compile_success": 0.0,
                "combined_score": 0.0,
                "artifacts": {
                    "feedback": "\n".join(
                        part
                        for part in [
                            "Compilation failed.",
                            _truncate(compile_result.get("stderr", "")),
                            _truncate(compile_result.get("stdout", "")),
                        ]
                        if part
                    ),
                    **_safety_artifacts(compile_result, {}, "Compile"),
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

        artifacts = _safety_artifacts(
            compile_result,
            results,
            "Full Checks" if full else "Smoke Checks",
        )

        metrics: Dict[str, float] = {
            "compile_success": 1.0,
            "safety_score": float(safety_score),
            "combined_score": float(safety_score),
        }

        for testcase, result in results.items():
            key = testcase.lower()
            metrics[f"{key}_safe"] = 1.0 if result["passed"] else 0.0

        if not full:
            metrics["smoke_safety_score"] = float(safety_score)
            metrics["combined_score"] = float(safety_score)
            artifacts["feedback"] = artifacts["smoke_checks_feedback"]
            return {**metrics, "artifacts": artifacts}

        verbose_outdir = run_root / "verbose_proxy"
        verbose_result = _run_check(
            dll_path,
            "tcProxyLSI",
            VERBOSE_SCHEDULES,
            verbose_outdir,
            verbose=True,
        )

        efficiency = _extract_efficiency_metrics(verbose_outdir if verbose_result["passed"] else run_root)
        metrics.update(efficiency)
        metrics["full_target_command_safe"] = metrics.get("tcproxylsi_safe", 0.0)

        all_full_safe = pass_count == len(results)
        if all_full_safe:
            metrics["combined_score"] = (
                0.7
                + 0.15 * metrics["rpc_efficiency"]
                + 0.1 * metrics["cache_hit_rate"]
                + 0.05 * metrics["transfer_efficiency"]
            )
        else:
            metrics["combined_score"] = 0.0

        feedback_lines = [
            artifacts["full_checks_feedback"],
            "",
            "Efficiency snapshot",
            f"- cache_hit_rate={metrics['cache_hit_rate']:.4f}",
            f"- rpc_per_client_op={metrics['rpc_per_client_op']:.4f}",
            f"- control_rpcs_per_transfer={metrics['control_rpcs_per_transfer']:.4f}",
            f"- db_rpcs={metrics['db_rpcs']:.0f}",
            f"- control_rpcs={metrics['control_rpcs']:.0f}",
            f"- ownership_transfers={metrics['ownership_transfers']:.0f}",
        ]
        artifacts["feedback"] = "\n".join(feedback_lines)

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
