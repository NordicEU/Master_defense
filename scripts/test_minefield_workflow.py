from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.input_app.app import build_risk_assessment, build_submission_payload  # noqa: E402

GATEWAY_URL = "http://127.0.0.1:8000/route"

TEST_CASE = {
    "name": "minefield_workflow_case",
    "person_id": "12345678901",
    "employer_id": "999888777",
    "declared_income": 50000,
    "declared_expenses": 950000,
    "employment_start": "01.01.2026",
    "employment_end": "31.12.2026",
}


def short(value: Any, max_len: int = 240) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def main() -> None:
    payload = build_submission_payload(
        person_id=TEST_CASE["person_id"],
        employer_id=TEST_CASE["employer_id"],
        declared_income=TEST_CASE["declared_income"],
        declared_expenses=TEST_CASE["declared_expenses"],
        employment_start=TEST_CASE["employment_start"],
        employment_end=TEST_CASE["employment_end"],
    )

    risk_assessment = build_risk_assessment(
        person_id=TEST_CASE["person_id"],
        employer_id=TEST_CASE["employer_id"],
        declared_income=TEST_CASE["declared_income"],
        declared_expenses=TEST_CASE["declared_expenses"],
        employment_start=TEST_CASE["employment_start"],
        employment_end=TEST_CASE["employment_end"],
    )

    gateway_payload = {
        "submission": payload["submission"],
        "normalized_payload": payload["normalized_payload"],
        "risk_assessment": risk_assessment,
    }

    with httpx.Client(timeout=30.0) as client:
        print("=" * 120)
        print("STEP 1: SEND MINEFIELD CASE THROUGH GATEWAY")
        print("=" * 120)
        gateway_response = client.post(GATEWAY_URL, json=gateway_payload)
        gateway_response.raise_for_status()
        gateway_result = gateway_response.json()
        print(short(gateway_result, 400))

        print("\n" + "=" * 120)
        print("SUMMARY")
        print("=" * 120)
        print(f"recommended_action : {risk_assessment.get('recommended_action')}")
        print(f"risk_score         : {risk_assessment.get('total_score')}")
        print(f"gateway_action     : {gateway_result.get('action')}")
        print(f"gateway_handoff    : {gateway_result.get('handoff')}")
        print(f"flow_result        : {gateway_result.get('flow_result')}")
        print(f"downstream_status  : {gateway_result.get('downstream_status')}")
        print(f"downstream_response: {short(gateway_result.get('downstream_response'), 400)}")

        report_path = ROOT / "runtime" / "minefield_workflow_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "test_case": TEST_CASE,
                    "risk_assessment": risk_assessment,
                    "gateway_result": gateway_result,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nSaved report: {report_path}")


if __name__ == "__main__":
    main()
