from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DECEIVER_URL = "http://127.0.0.1:8007/deception"
MINEFIELD_URL = "http://127.0.0.1:8006/defer"


def short(value: Any, max_len: int = 240) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def main() -> None:
    submission_id = f"deceiver-forward-{uuid4()}"

    payload = {
        "submission": {
            "submission_id": submission_id,
            "source": "deceiver_test",
            "payload_type": "tax_document",
            "received_at": "2026-04-09T00:00:00Z",
            "schema_version": "v1",
            "payload": {
                "data": {
                    "person_id": "12345678901",
                    "employer_id": "999888777",
                    "fields": {
                        "declared_income": 50000,
                        "declared_expenses": 980000,
                    },
                }
            },
        },
        "normalized_payload": {
            "person_id": "12345678901",
            "employer_id": "999888777",
            "declared_income": 50000,
            "declared_expenses": 980000,
        },
        "risk_assessment": {
            "assessment_id": f"dec-test-assessment-{uuid4()}",
            "rule_score": 0.92,
            "statistical_score": 0.94,
            "context_score": 0.91,
            "semantic_score": 0.88,
            "total_score": 0.93,
            "confidence": 0.92,
            "findings": [],
            "semantic_reasoning": "forged_context, hostile, fraud",
            "recommended_action": "DECEIVE",
            "assessed_at": "2026-04-09T00:00:00Z",
        },
        "decision_result": {
            "action": "DECEIVE",
            "handoff": "NONE",
            "policy_version": "v4_master",
            "reasons": ["deceptive_semantic_pattern_detected"],
            "confidence_label": "high",
        },
    }

    with httpx.Client(timeout=30.0) as client:
        print("=" * 120)
        print("STEP 1: CREATE DECEIVER CASE")
        print("=" * 120)
        create_resp = client.post(DECEIVER_URL, json=payload)
        create_resp.raise_for_status()
        created = create_resp.json()
        print(short(created, 400))
        case_id = created["case_id"]

        print("\n" + "=" * 120)
        print("STEP 2: FORWARD DECEIVER CASE TO MINEFIELD")
        print("=" * 120)
        forward_resp = client.post(
            f"{DECEIVER_URL}/{case_id}/minefield",
            json={
                "actor": "deceiver_agent",
                "confidence": 0.95,
                "reasoning": "Semantic deception is severe enough for direct minefield transfer.",
                "details": {"signal": "forged_context_confirmed"},
            },
        )
        forward_resp.raise_for_status()
        forwarded = forward_resp.json()
        print(short(forwarded, 500))

        print("\n" + "=" * 120)
        print("STEP 3: VERIFY MINEFIELD CASE LIST")
        print("=" * 120)
        mine_resp = client.get(MINEFIELD_URL)
        mine_resp.raise_for_status()
        cases = mine_resp.json().get("cases", [])
        match = None
        for case in cases:
            if case.get("submission", {}).get("submission_id") == submission_id:
                match = case
                break
        if match is None:
            raise RuntimeError("No minefield case found for forwarded deceiver submission.")
        print(short(match, 400))

        report = {
            "submission_id": submission_id,
            "deceiver_case_id": case_id,
            "forward_result": forwarded,
            "minefield_case": match,
        }
        report_path = ROOT / "runtime" / "deceiver_to_minefield_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved report: {report_path}")


if __name__ == "__main__":
    main()
