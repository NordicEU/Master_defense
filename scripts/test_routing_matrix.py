from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.input_app.app import build_risk_assessment, build_submission_payload  # noqa: E402

GATEWAY_URL = "http://127.0.0.1:8000/route"


TEST_CASES: List[Dict[str, Any]] = [
    {
        "name": "normal_allow",
        "expected_actions": {"ALLOW"},
        "person_id": "12345678901",
        "employer_id": "999888777",
        "declared_income": 520000,
        "declared_expenses": 45000,
        "employment_start": "01.01.2026",
        "employment_end": "31.12.2026",
    },
    {
        "name": "balanced_but_high_expense",
        "expected_actions": {"ALLOW"},
        "person_id": "12345678901",
        "employer_id": "999888777",
        "declared_income": 340000,
        "declared_expenses": 280000,
        "employment_start": "01.01.2026",
        "employment_end": "31.12.2026",
    },
    {
        "name": "high_contain_ratio",
        "expected_actions": {"CONTAIN"},
        "person_id": "12345678901",
        "employer_id": "999888777",
        "declared_income": 200000,
        "declared_expenses": 500000,
        "employment_start": "01.01.2026",
        "employment_end": "31.12.2026",
    },
    {
        "name": "extreme_contain_or_minefield",
        "expected_actions": {"CONTAIN", "MINEFIELD"},
        "person_id": "12345678901",
        "employer_id": "999888777",
        "declared_income": 904000,
        "declared_expenses": 999999999,
        "employment_start": "01.01.2026",
        "employment_end": "31.12.2026",
    },
    {
        "name": "invalid_person_id",
        "expected_actions": {"CONTAIN"},
        "person_id": "180401",
        "employer_id": "397049",
        "declared_income": 340000,
        "declared_expenses": 280000,
        "employment_start": "01.01.2026",
        "employment_end": "31.12.2026",
    },
    {
        "name": "bad_dates",
        "expected_actions": {"CONTAIN"},
        "person_id": "12345678901",
        "employer_id": "999888777",
        "declared_income": 400000,
        "declared_expenses": 50000,
        "employment_start": "31.12.2026",
        "employment_end": "01.01.2026",
    },
    {
        "name": "low_income_high_expenses",
        "expected_actions": {"CONTAIN", "MINEFIELD"},
        "person_id": "12345678901",
        "employer_id": "999888777",
        "declared_income": 50000,
        "declared_expenses": 950000,
        "employment_start": "01.01.2026",
        "employment_end": "31.12.2026",
    },
]


def short_json(value: Any, max_len: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def run_case(client: httpx.Client, case: Dict[str, Any]) -> Dict[str, Any]:
    payload = build_submission_payload(
        person_id=case["person_id"],
        employer_id=case["employer_id"],
        declared_income=case["declared_income"],
        declared_expenses=case["declared_expenses"],
        employment_start=case["employment_start"],
        employment_end=case["employment_end"],
    )

    risk_assessment = build_risk_assessment(
        person_id=case["person_id"],
        employer_id=case["employer_id"],
        declared_income=case["declared_income"],
        declared_expenses=case["declared_expenses"],
        employment_start=case["employment_start"],
        employment_end=case["employment_end"],
    )

    gateway_payload = {
        "submission": payload["submission"],
        "normalized_payload": payload["normalized_payload"],
        "risk_assessment": risk_assessment,
    }

    try:
        response = client.post(GATEWAY_URL, json=gateway_payload)
        response.raise_for_status()
        result = response.json()
        action = result.get("action")
        passed = action in case["expected_actions"]
        return {
            "name": case["name"],
            "expected_actions": sorted(case["expected_actions"]),
            "passed": passed,
            "risk_score": risk_assessment.get("total_score"),
            "recommended_action": risk_assessment.get("recommended_action"),
            "semantic_reasoning": risk_assessment.get("semantic_reasoning"),
            "action": action,
            "handoff": result.get("handoff"),
            "flow_result": result.get("flow_result"),
            "downstream_status": result.get("downstream_status"),
            "downstream_response": result.get("downstream_response"),
        }
    except Exception as exc:
        return {
            "name": case["name"],
            "expected_actions": sorted(case["expected_actions"]),
            "passed": False,
            "risk_score": risk_assessment.get("total_score"),
            "recommended_action": risk_assessment.get("recommended_action"),
            "semantic_reasoning": risk_assessment.get("semantic_reasoning"),
            "action": "ERROR",
            "handoff": "ERROR",
            "flow_result": "ERROR",
            "downstream_status": None,
            "downstream_response": str(exc),
        }


def main() -> None:
    print("=" * 140)
    print("ROUTING MATRIX TEST")
    print("=" * 140)

    results: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    with httpx.Client(timeout=30.0) as client:
        for case in TEST_CASES:
            result = run_case(client, case)
            results.append(result)
            counts[result["action"]] = counts.get(result["action"], 0) + 1

    header = (
        f"{'CASE':<28}"
        f"{'PASS':<8}"
        f"{'RISK':<8}"
        f"{'REC':<10}"
        f"{'ACTION':<12}"
        f"{'HANDOFF':<24}"
        f"{'EXPECTED':<22}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        print(
            f"{r['name']:<28}"
            f"{str(r['passed']):<8}"
            f"{str(r['risk_score']):<8}"
            f"{str(r['recommended_action']):<10}"
            f"{str(r['action']):<12}"
            f"{str(r['handoff']):<24}"
            f"{','.join(r['expected_actions']):<22}"
        )

    print("\nACTION COUNTS")
    print("=" * 140)
    for action, count in sorted(counts.items()):
        print(f"{action:<20} {count}")

    print("\nDETAILS")
    print("=" * 140)
    for r in results:
        print(f"\n[{r['name']}]")
        print(f"expected_actions    : {r['expected_actions']}")
        print(f"passed              : {r['passed']}")
        print(f"risk_score          : {r['risk_score']}")
        print(f"recommended_action  : {r['recommended_action']}")
        print(f"semantic_reasoning  : {r['semantic_reasoning']}")
        print(f"action              : {r['action']}")
        print(f"handoff             : {r['handoff']}")
        print(f"flow_result         : {r['flow_result']}")
        print(f"downstream_status   : {r['downstream_status']}")
        print(f"downstream_response : {short_json(r['downstream_response'])}")

    report_path = ROOT / "runtime" / "routing_matrix_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nSaved report:")
    print(report_path)


if __name__ == "__main__":
    main()
