from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from typing import Any, Dict

import httpx


def build_command(target: str) -> list[str]:
    system = platform.system().lower()
    if system == "windows":
        return ["tracert", "-d", target]
    return ["traceroute", "-n", target]


def run_trace(target: str) -> Dict[str, Any]:
    command = build_command(target)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return {
            "command": " ".join(command),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {
            "command": " ".join(command),
            "stdout": "",
            "stderr": str(exc),
            "returncode": 1,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a manual analyst trace and store the result on a minefield case.")
    parser.add_argument("--case-id", required=True, help="Minefield defer_id")
    parser.add_argument("--target", required=True, help="Target host or IP to trace")
    parser.add_argument("--actor", default="minefield_operator", help="Analyst actor name")
    parser.add_argument(
        "--service-base",
        default="http://127.0.0.1:8006",
        help="Base URL for the minefield service",
    )
    args = parser.parse_args()

    trace_result = run_trace(args.target)

    payload = {
        "actor": args.actor,
        "target": args.target,
        "command": trace_result["command"],
        "stdout": trace_result["stdout"],
        "stderr": trace_result["stderr"],
        "returncode": trace_result["returncode"],
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(f"{args.service_base}/defer/{args.case_id}/trace-results", json=payload)
        response.raise_for_status()
        print(response.text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
