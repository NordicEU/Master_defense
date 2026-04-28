from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from services.quarantine_service import app as quarantine_app_module
from services.quarantine_service.app import app


client = TestClient(app)


def quarantine_payload() -> dict:
    return {
        "submission": {
            "submission_id": "test-submission-001",
            "source": "dataset_replay",
            "payload_type": "tax_document",
            "received_at": "2026-04-09T00:00:00Z",
            "correlation_id": None,
            "schema_version": "v1",
            "payload": {
                "data": {
                    "document_type": "SKATTEPLIKT_2025",
                    "person_id": "11111111111",
                    "partsnummer": "3000011111",
                    "inntektsaar": "2025",
                    "fields": {
                        "skatteplikt_til_norge": "true"
                    }
                }
            }
        },
        "normalized_payload": {
            "document_type": "SKATTEPLIKT_2025",
            "person_id": "11111111111",
            "partsnummer": "3000011111",
            "inntektsaar": "2025",
            "fields": {
                "skatteplikt_til_norge": "true"
            }
        },
        "risk_assessment": {
            "assessment_id": "risk-test-001",
            "rule_score": 0.35,
            "statistical_score": 0.30,
            "context_score": 0.82,
            "semantic_score": 0.10,
            "total_score": 0.52,
            "confidence": 0.84,
            "findings": [],
            "semantic_reasoning": "Semantic layer did not override containment.",
            "recommended_action": "REVIEW",
            "assessed_at": "2026-04-09T00:00:00Z"
        },
        "decision_result": {
            "decision_id": "decision-test-001",
            "action": "QUARANTINE",
            "policy_version": "v_final",
            "reasons": [
                "context_mismatch",
                "policy_containment"
            ],
            "decided_at": "2026-04-09T00:00:00Z"
        }
    }


def setup_runtime_dirs(tmp_path: Path):
    quarantine_dir = tmp_path / "quarantine_cases"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    audit_dir = tmp_path / "audit_logs"
    audit_dir.mkdir(parents=True, exist_ok=True)

    quarantine_app_module.QUARANTINE_DIR = quarantine_dir

    from shared.utils import audit_logger
    audit_logger.QUARANTINE_AUDIT_PATH = audit_dir / "quarantine_audit.jsonl"

    return quarantine_dir, audit_dir


def test_create_and_get_quarantine_case(tmp_path):
    quarantine_dir, audit_dir = setup_runtime_dirs(tmp_path)

    response = client.post("/quarantine", json=quarantine_payload())
    assert response.status_code == 200

    body = response.json()
    assert body["message"] == "Submission quarantined successfully."
    assert body["status"] == "ISOLATED"
    assert body["severity"] == "HIGH"
    assert body["isolation_mode"] == "FULL_CONTAINMENT"

    case_id = body["case_id"]

    case_file = quarantine_dir / f"{case_id}.json"
    assert case_file.exists()

    get_response = client.get(f"/quarantine/{case_id}")
    assert get_response.status_code == 200

    case_data = get_response.json()
    assert case_data["case_id"] == case_id
    assert case_data["current_state"] == "ISOLATED"
    assert case_data["severity"] == "HIGH"
    assert case_data["isolation_mode"] == "FULL_CONTAINMENT"

    audit_path = audit_dir / "quarantine_audit.jsonl"
    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "CASE_CREATED"


def test_list_quarantine_cases(tmp_path):
    setup_runtime_dirs(tmp_path)

    create_response = client.post("/quarantine", json=quarantine_payload())
    assert create_response.status_code == 200

    list_response = client.get("/quarantine")
    assert list_response.status_code == 200

    cases = list_response.json()["cases"]
    assert len(cases) == 1
    assert cases[0]["status"] == "ISOLATED"
    assert cases[0]["decision"] == "QUARANTINE"


def test_update_quarantine_case_state(tmp_path):
    quarantine_dir, audit_dir = setup_runtime_dirs(tmp_path)

    create_response = client.post("/quarantine", json=quarantine_payload())
    case_id = create_response.json()["case_id"]

    update_response = client.post(
        f"/quarantine/{case_id}/state",
        json={
            "new_state": "UNDER_REVIEW",
            "actor": "ops_analyst",
            "message": "Case moved to analyst review.",
            "details": {"ticket": "OPS-1001"},
        },
    )
    assert update_response.status_code == 200
    body = update_response.json()

    assert body["old_state"] == "ISOLATED"
    assert body["new_state"] == "UNDER_REVIEW"

    get_response = client.get(f"/quarantine/{case_id}")
    case_data = get_response.json()
    assert case_data["current_state"] == "UNDER_REVIEW"
    assert len(case_data["audit_trail"]) == 2

    audit_path = audit_dir / "quarantine_audit.jsonl"
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    record = json.loads(lines[-1])
    assert record["event_type"] == "STATE_CHANGED"


def test_quarantine_metrics_endpoints(tmp_path):
    setup_runtime_dirs(tmp_path)

    create_response = client.post("/quarantine", json=quarantine_payload())
    assert create_response.status_code == 200

    metrics_json = client.get("/quarantine/metrics")
    assert metrics_json.status_code == 200
    metrics_data = metrics_json.json()
    assert metrics_data["total_cases"] == 1
    assert metrics_data["cases_by_state"]["ISOLATED"] == 1

    metrics_prom = client.get("/metrics")
    assert metrics_prom.status_code == 200
    assert "quarantine_cases_total 1" in metrics_prom.text
