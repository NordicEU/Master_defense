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
QUARANTINE_URL = "http://127.0.0.1:8003/quarantine"

TEST_CASE = {
    "name": "containment_workflow_case",
    "person_id": "12345678901",
    "employer_id": "999888777",
    "declared_income": 200000,
    "declared_expenses": 500000,
    "employment_start": "01.01.2026",
    "employment_end": "31.12.2026",
}


def short(value: Any, max_len: int = 240) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def find_case_by_submission_id(client: httpx.Client, submission_id: str) -> Dict[str, Any]:
    response = client.get(QUARANTINE_URL)
    response.raise_for_status()
    cases = response.json().get("cases", [])
    for case in cases:
        if case.get("submission_id") == submission_id:
            return case
    raise RuntimeError(f"No containment case found for submission_id={submission_id}")


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

    submission_id = payload["submission"]["submission_id"]

    with httpx.Client(timeout=30.0) as client:
        print("=" * 120)
        print("STEP 1: SEND CONTAINMENT CASE THROUGH GATEWAY")
        print("=" * 120)
        gateway_response = client.post(GATEWAY_URL, json=gateway_payload)
        gateway_response.raise_for_status()
        gateway_result = gateway_response.json()
        print(short(gateway_result, 400))

        if gateway_result.get("action") != "CONTAIN":
            raise RuntimeError(
                f"Expected CONTAIN for containment workflow test, got {gateway_result.get('action')}"
            )

        print("\n" + "=" * 120)
        print("STEP 2: FIND MATCHING CONTAINMENT CASE BY SUBMISSION ID")
        print("=" * 120)
        matched_case = find_case_by_submission_id(client, submission_id)
        case_id = matched_case["case_id"]
        print(f"submission_id  : {submission_id}")
        print(f"matched_case_id: {case_id}")
        print(short(matched_case, 400))

        print("\n" + "=" * 120)
        print("STEP 3: GET FULL CASE BEFORE ANALYZE")
        print("=" * 120)
        case_before = client.get(f"{QUARANTINE_URL}/{case_id}")
        case_before.raise_for_status()
        before_json = case_before.json()
        print(f"state_before: {before_json.get('current_state')}")
        print(f"risk_score  : {before_json.get('risk_assessment', {}).get('total_score')}")
        print(f"severity    : {before_json.get('severity')}")

        print("\n" + "=" * 120)
        print("STEP 4: ANALYZE CASE")
        print("=" * 120)
        analyze_response = client.post(f"{QUARANTINE_URL}/{case_id}/analyze")
        analyze_response.raise_for_status()
        advisory = analyze_response.json()
        print(short(advisory, 400))

        print("\n" + "=" * 120)
        print("STEP 5: APPLY ADVISORY")
        print("=" * 120)
        apply_response = client.post(
            f"{QUARANTINE_URL}/{case_id}/apply-advisory",
            json={"actor": "containment_policy", "force_human_override": True},
        )
        apply_response.raise_for_status()
        applied = apply_response.json()
        print(short(applied, 400))

        print("\n" + "=" * 120)
        print("STEP 6: GET FULL CASE AFTER APPLY")
        print("=" * 120)
        case_after = client.get(f"{QUARANTINE_URL}/{case_id}")
        case_after.raise_for_status()
        after_json = case_after.json()
        print(f"state_after              : {after_json.get('current_state')}")
        print(f"transfer_target          : {after_json.get('transfer_target')}")
        print(f"requires_human_oversight : {after_json.get('requires_human_oversight')}")
        print(f"audit_events             : {len(after_json.get('audit_trail', []))}")
        print(f"observations             : {len(after_json.get('observations', []))}")

        print("\n" + "=" * 120)
        print("SUMMARY")
        print("=" * 120)
        print(f"submission_id       : {submission_id}")
        print(f"recommended_action  : {risk_assessment.get('recommended_action')}")
        print(f"risk_score          : {risk_assessment.get('total_score')}")
        print(f"gateway_action      : {gateway_result.get('action')}")
        print(f"gateway_handoff     : {gateway_result.get('handoff')}")
        print(f"final_state         : {after_json.get('current_state')}")
        print(f"transfer_target     : {after_json.get('transfer_target')}")

        report_path = ROOT / "runtime" / "containment_workflow_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "test_case": TEST_CASE,
                    "submission_id": submission_id,
                    "risk_assessment": risk_assessment,
                    "gateway_result": gateway_result,
                    "case_id": case_id,
                    "advisory": advisory,
                    "apply_result": applied,
                    "final_case": after_json,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nSaved report: {report_path}")


if __name__ == "__main__":
    main()
