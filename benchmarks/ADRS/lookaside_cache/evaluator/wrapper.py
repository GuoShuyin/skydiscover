"""Backwards-compat wrapper for old Python-based evaluators.

Old-style evaluators define ``evaluate(program_path) -> dict``.  This module
bridges that interface to the container JSON protocol expected by
ContainerizedEvaluator.
"""

import json
import sys
import traceback


def run(evaluate_fn):
    if len(sys.argv) < 2:
        print("Usage: evaluator.py <program_path>", file=sys.stderr)
        sys.exit(1)

    program_path = sys.argv[1]

    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        result = evaluate_fn(program_path)
    except Exception as exc:
        sys.stdout = real_stdout
        print(
            json.dumps(
                {
                    "status": "error",
                    "combined_score": 0.0,
                    "metrics": {"combined_score": 0.0},
                    "artifacts": {
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                }
            )
        )
        return
    sys.stdout = real_stdout

    if not isinstance(result, dict):
        print(
            json.dumps(
                {
                    "status": "error",
                    "combined_score": 0.0,
                    "metrics": {"combined_score": 0.0},
                    "artifacts": {
                        "error": f"evaluate() returned {type(result).__name__}, expected dict"
                    },
                }
            )
        )
        return

    metrics = {}
    artifacts = {}
    for key, value in result.items():
        if isinstance(value, bool):
            metrics[key] = float(value)
        elif isinstance(value, (int, float)):
            metrics[key] = float(value)
        elif isinstance(value, str):
            artifacts[key] = value
        elif isinstance(value, (list, dict)):
            artifacts[key] = json.dumps(value)

    if "combined_score" not in metrics:
        metrics["combined_score"] = 0.0

    status = "error" if "error" in artifacts else "success"
    output = {
        "status": status,
        "combined_score": metrics["combined_score"],
        "metrics": metrics,
    }
    if artifacts:
        output["artifacts"] = artifacts

    print(json.dumps(output))
