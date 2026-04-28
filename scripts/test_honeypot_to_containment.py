from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HONEYPOT_URL = "http://127.0.0.1:8005/review"
QUARANTINE_URL = "http://127.0.0.1:8003/quarantine"


def short(value: Any, max_len: int = 240) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def find_case_by_submission_id(client: httpx.Client, submission_id: str) -> Dict[str, Any]:
    response = client.get(QUARANTINE_URL)
    response.raise_for_status()
    for case in response.json().get("cases", []):
        if case.get("submission_id") == submission_id:
            return case
    raise RuntimeError(f"No containment case found for submission_id={submission_id}")


def main() -> None:
    submission_id = f"honeypot-forward-{uuid4()}"

    payload = {
        "submission": {
            "submission_id": submission_id,
            "source": "honeypot_test",
            "payload_type": "tax_document",
            "received_at": "2026-04-09T00:00:00Z",
            "schema_version": "v1",
            "payload": {
                "data": {
                    "person_id": "12345678901",
                    "employer_id": "999888777",
                    "fields": {
                        "declared_income": 210000,
                        "declared_expenses": 510000,
                    },
                }
            },
        },
        "normalized_payload": {
            "person_id": "12345678901",
            "employer_id": "999888777",
            "declared_income": 210000,
            "declared_expenses": 510000,
        },
        "risk_assessment": {
            "assessment_id": f"hp-test-assessment-{uuid4()}",
            "rule_score": 0.70,
            "statistical_score": 0.68,
            "context_score": 0.72,
            "semantic_score": 0.60,
            "total_score": 0.71,
            "confidence": 0.85,
            "findings": [],
            "semantic_reasoning": "probing, suspicious_behavior_pattern",
            "recommended_action": "HONEYPOT",
            "assessed_at": "2026-04-09T00:00:00Z",
        },
        "decision_result": {
            "action": "HONEYPOT",
            "handoff": "NONE",
            "policy_version": "v4_master",
            "reasons": ["behavioral_probing_detected"],
            "confidence_label": "medium",
        },
    }

    with httpx.Client(timeout=30.0) as client:
        print("=" * 120)
        print("STEP 1: CREATE HONEYPOT CASE")
        print("=" * 120)
        create_resp = client.post(HONEYPOT_URL, json=payload)
        create_resp.raise_for_status()
        created = create_resp.json()
        print(short(created, 400))
        case_id = created["case_id"]

        print("\n" + "=" * 120)
        print("STEP 2: FORWARD HONEYPOT CASE TO CONTAINMENT")
        print("=" * 120)
        forward_resp = client.post(
            f"{HONEYPOT_URL}/{case_id}/contain",
            json={
                "actor": "honeypot_agent",
                "confidence": 0.87,
                "reasoning": "Observed suspicious interaction pattern; forwarding to containment.",
                "details": {"signal": "probing_confirmed"},
            },
        )
        forward_resp.raise_for_status()
        forwarded = forward_resp.json()
        print(short(forwarded, 500))

        print("\n" + "=" * 120)
        print("STEP 3: VERIFY CONTAINMENT CASE")
        print("=" * 120)
        matched = find_case_by_submission_id(client, submission_id)
        print(short(matched, 400))

        report = {
            "submission_id": submission_id,
            "honeypot_case_id": case_id,
            "forward_result": forwarded,
            "containment_case": matched,
        }
        report_path = ROOT / "runtime" / "honeypot_to_containment_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved report: {report_path}")


if __name__ == "__main__":
    main()
