#!/usr/bin/env python3
"""Runtime-capable P scorer: compile, static latency proxy, and LSI via P checker."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

BUGS_FOUND_RE = re.compile(r"Found\s+(\d+)\s+bug(?:s)?\b", re.IGNORECASE)
SEND_RE = re.compile(r"\bsend\b", re.MULTILINE)
REQUIRED_ARTIFACT_PATH = "PSrc/Machines.p"

PROFILE_STAGE1 = "stage1"
PROFILE_STAGE2 = "stage2"

LSI_TESTCASES = (
    "tcOwnershipSafetyLSIOnly",
    "tcDelayWriteFocused",
    "tcProxyLSI",
)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_pproj(root: Path) -> None:
    template = _read_text(_project_root() / "OwnershipSafety.pproj")
    impl = sorted(root.glob("PSrc/**/*.p"))
    lines = ["  <InputFiles>"]
    for p in impl:
        rel = "./" + p.relative_to(root).as_posix()
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
    (root / "OwnershipSafety.pproj").write_text(rewritten + ("" if rewritten.endswith("\n") else "\n"), encoding="utf-8")


def _materialize_workspace(program_text: str, root: Path) -> List[str]:
    """Write the generated PSrc file and copy fixed repo artifacts."""
    notes: List[str] = []
    psrc = root / "PSrc"
    psrc.mkdir(parents=True, exist_ok=True)
    target = root / REQUIRED_ARTIFACT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(program_text, encoding="utf-8")

    repo = _project_root()
    (root / "PSpec").mkdir(parents=True, exist_ok=True)
    (root / "PTst").mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / "PSpec" / "Spec.p", root / "PSpec" / "Spec.p", follow_symlinks=True)
    shutil.copy2(repo / "PTst" / "TestDriver.p", root / "PTst" / "TestDriver.p", follow_symlinks=True)
    shutil.copy2(repo / "PTst" / "TestScript.p", root / "PTst" / "TestScript.p", follow_symlinks=True)
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


_STORAGE_SEND_RE = re.compile(
    r"\bsend\s+[^,;]+,\s*e(?:DbRead|DbWrite|GetSplitPoints|SetEpoch)\b",
)
_COORD_RE = re.compile(r"\beRequestOwnership(?:Grant|Revoke)\b")


def _latency_stats(text: str) -> Tuple[int, int, int, int]:
    lines = max(1, len(text.splitlines()))
    sends = len(SEND_RE.findall(text))
    storage = len(_STORAGE_SEND_RE.findall(text))
    coord = len(_COORD_RE.findall(text))
    return lines, sends, storage, coord


def _latency_proxy_score(impl_paths: List[Path]) -> Tuple[float, Dict[str, float]]:
    """Use an absolute structural cost heuristic for logical request latency."""
    full = "\n".join(_read_text(p) for p in impl_paths)
    lines, sends, storage_hops, coord = _latency_stats(full)

    send_density = sends / float(lines)
    storage_density = storage_hops / float(lines)
    coord_density = coord / float(lines)

    density_penalty = _clamp(max(0.0, send_density - 0.055) / 0.055 * 0.40)
    storage_penalty = _clamp(max(0.0, storage_density - 0.018) / 0.018 * 0.40)
    coord_penalty = _clamp(max(0.0, coord_density - 0.006) / 0.006 * 0.20)

    raw = 1.0 - density_penalty - storage_penalty - coord_penalty
    score = _clamp(raw)
    detail = {
        "impl_lines": float(lines),
        "impl_sends": float(sends),
        "send_density_per_100_lines": float(sends / lines * 100.0),
        "storage_like_sends_est": float(storage_hops),
        "ownership_request_events_est": float(coord),
        "latency_proxy_score": float(score),
    }
    return score, detail


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
    for m in BUGS_FOUND_RE.finditer(output):
        n = int(m.group(1))
        best = n if best is None else max(best, n)
    return best


def _run_lsi_case(dll: Path, testcase: str, schedules: int, timeout: int, workspace: Path) -> Tuple[bool, str, int | None]:
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
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    bugs = _parse_bug_count(out)
    if bugs is None:
        return False, out, None
    return bugs == 0 and proc.returncode == 0, out, bugs


def _compile_artifact_score(program_text: str, psrc_files: List[Path]) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if not psrc_files:
        notes.append(f"No implementation file found at `{REQUIRED_ARTIFACT_PATH}`.")
        return 0.0, notes
    if not program_text.strip():
        notes.append(f"`{REQUIRED_ARTIFACT_PATH}` is empty.")
        return 0.0, notes
    nonempty = [p for p in psrc_files if p.read_text(encoding="utf-8", errors="replace").strip()]
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
        return _clamp(0.48 * compile_ok + 0.42 * latency + 0.10 * lsi_part)

    # stage2: LSI hard gate
    if not lsi_ran:
        return _clamp(0.12 * compile_ok + 0.08 * latency)
    if not lsi_pass:
        return _clamp(0.02 * compile_ok)
    return _clamp(0.42 * compile_ok + 0.33 * latency + 0.25 * 1.0)


def evaluate(program_path: str) -> Dict[str, object]:
    profile = os.environ.get("P_SCORER_PROFILE", PROFILE_STAGE2).strip().lower()
    if profile not in (PROFILE_STAGE1, PROFILE_STAGE2):
        profile = PROFILE_STAGE2

    compile_timeout = int(os.environ.get("P_SCORER_COMPILE_TIMEOUT", "240"))
    check_timeout = int(os.environ.get("P_SCORER_CHECK_TIMEOUT", "90"))
    schedules = int(os.environ.get("P_SCORER_LSI_SCHEDULES", "4" if profile == PROFILE_STAGE1 else "12"))

    repo = _project_root()

    try:
        program_text = _read_text(Path(program_path))
    except Exception as exc:
        return {
            "combined_score": 0.0,
            "metrics": {"combined_score": 0.0, "evaluator_exception": 1.0},
            "artifacts": {"error": f"{type(exc).__name__}: {exc}"},
        }

    try:
        return _evaluate_workspace(program_text, profile, compile_timeout, check_timeout, schedules, repo)
    except subprocess.TimeoutExpired as exc:
        return {
            "combined_score": 0.0,
            "metrics": {"combined_score": 0.0, "evaluator_timeout": 1.0, "profile": profile},
            "artifacts": {"error": f"Subprocess timeout: {exc}"},
        }
    except Exception as exc:
        return {
            "combined_score": 0.0,
            "metrics": {"combined_score": 0.0, "evaluator_exception": 1.0, "profile": profile},
            "artifacts": {"error": f"{type(exc).__name__}: {exc}"},
        }


def _evaluate_workspace(
    program_text: str,
    profile: str,
    compile_timeout: int,
    check_timeout: int,
    schedules: int,
    repo: Path,
) -> Dict[str, object]:
    feedback_lines: List[str] = []
    metrics: Dict[str, float | str] = {"profile": profile}

    with tempfile.TemporaryDirectory(prefix="p_scorer_") as tmp:
        tmp_path = Path(tmp)
        mat_notes = _materialize_workspace(program_text, tmp_path)
        psrc_files = _list_psrc_files(tmp_path)

        struct_score, struct_notes = _compile_artifact_score(program_text, psrc_files)
        for n in mat_notes + struct_notes:
            feedback_lines.append(f"- {n}")

        latency, lat_detail = _latency_proxy_score(psrc_files)
        metrics.update({k: float(v) for k, v in lat_detail.items()})

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
        lsi_details: List[str] = []
        bugs_total = 0

        if compile_ok >= 1.0:
            dll = _find_checker_dll(tmp_path / "PGenerated", "OwnershipSafety")
            if dll is None:
                feedback_lines.append("Compile reported success but no checker DLL was found.")
            else:
                for tc in LSI_TESTCASES:
                    lsi_ran = True
                    passed, _log, bugs = _run_lsi_case(dll, tc, schedules, check_timeout, tmp_path)
                    if bugs is None:
                        lsi_pass = False
                        lsi_details.append(f"{tc}: checker output unparsable (see logs).")
                        feedback_lines.append(f"LSI check {tc}: could not parse bug count; treating as failure.")
                        break
                    bugs_total += bugs
                    if not passed:
                        lsi_pass = False
                        lsi_details.append(f"{tc}: found {bugs} bug(s)")
                        feedback_lines.append(f"LSI check {tc}: Found {bugs} bug(s).")
                        break
                    lsi_details.append(f"{tc}: 0 bugs")
                else:
                    lsi_pass = True

        metrics["lsi_pass"] = 1.0 if lsi_pass else 0.0
        metrics["lsi_checks_ran"] = 1.0 if lsi_ran else 0.0
        metrics["latency_proxy_score"] = float(effective_latency)

        combined = _combined_score(profile, metrics["compile_score"], effective_latency, lsi_pass, lsi_ran)
        metrics["combined_score"] = float(combined)

        feedback_lines.insert(
            0,
            "Scores (read together):\n"
            "  (1) LSI correctness — PChecker on fixed Spec/tests; dominant in stage2 (hard gate on any LSI bug).\n"
            "  (2) Logical request latency — static proxy from implementation PSrc: send density and "
            "estimated storage/coordination hops; direct storage reads/writes and extra round trips are costly "
            "(lower structural cost → higher score).\n"
            f"  (3) Syntax / compile — non-empty generated `{REQUIRED_ARTIFACT_PATH}` source plus successful `p compile`.\n",
        )
        feedback_lines.insert(1, f"Profile={profile} combined_score={combined:.4f}")
        feedback_lines.insert(
            2,
            f"  compile_score={metrics['compile_score']:.4f}  "
            f"latency_proxy={effective_latency:.4f}  "
            f"lsi_pass={bool(lsi_pass)} (bugs_total={bugs_total})",
        )
        if profile == PROFILE_STAGE1:
            feedback_lines.insert(
                3,
                "  stage1: LSI is reported but weighted lightly; compile and latency proxy drive the combined score.",
            )
        else:
            feedback_lines.insert(
                3,
                "  stage2: any LSI violation collapses the combined score toward 0; passing LSI unlocks full weighting.",
            )

        artifacts: Dict[str, str] = {"feedback": "\n".join(feedback_lines)}
        if compile_log.strip():
            artifacts["compile_log_tail"] = compile_log[-8000:]
        if lsi_details:
            artifacts["lsi_summary"] = "; ".join(lsi_details)

        return {
            "combined_score": float(combined),
            "metrics": metrics,
            "artifacts": artifacts,
        }


if __name__ == "__main__":
    import sys

    print(json.dumps(evaluate(sys.argv[1]), indent=2))
