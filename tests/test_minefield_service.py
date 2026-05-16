from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from services.defer_service import app as minefield_module


client = TestClient(minefield_module.app)


def make_payload() -> dict:
    return {
        "submission": {
            "submission_id": "minefield-submission-001",
            "source": "pytest",
        },
        "normalized_payload": {
            "person_id": "12345678901",
            "employer_id": "999888777",
            "declared_income": 50000,
            "declared_expenses": 950000,
        },
        "risk_assessment": {
            "total_score": 0.93,
            "confidence": 0.92,
            "recommended_action": "MINEFIELD",
        },
        "decision_result": {
            "action": "MINEFIELD",
            "handoff": "ESCALATE",
            "policy_version": "v5_master",
            "reasons": ["minefield_threshold_met"],
            "confidence_label": "high",
        },
        "source_agent": "gateway",
    }


def setup_minefield_dir(tmp_path: Path) -> Path:
    minefield_dir = tmp_path / "defer_cases"
    minefield_dir.mkdir(parents=True, exist_ok=True)
    minefield_module.MINEFIELD_DIR = minefield_dir
    return minefield_dir


def test_create_minefield_case_persists_minefield_controls(tmp_path: Path) -> None:
    minefield_dir = setup_minefield_dir(tmp_path)

    response = client.post("/defer", json=make_payload())
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "queued"
    assert body["submission_id"] == "minefield-submission-001"

    stored = minefield_module.load_case(body["defer_id"])
    assert stored["status"] == "queued"
    progressive_delay = stored["minefield_controls"]["progressive_delay"]
    assert progressive_delay["status"] == "active"
    assert progressive_delay["enabled"] is True
    assert progressive_delay["recommended_delay_seconds"] == 20
    assert "extreme_risk_score" in progressive_delay["reasons"]
    assert stored["minefield_controls"]["behavior_capture"]["status"] == "active"
    assert stored["minefield_controls"]["link_analysis"]["status"] == "active"
    assert stored["minefield_controls"]["auto_blacklist"]["enabled"] is False
    assert stored["minefield_controls"]["auto_blacklist"]["status"] == "placeholder"
    assert (minefield_dir / f'{body["defer_id"]}.json').exists()


def test_minefield_case_supports_status_updates_and_notes(tmp_path: Path) -> None:
    setup_minefield_dir(tmp_path)

    create_response = client.post("/defer", json=make_payload())
    defer_id = create_response.json()["defer_id"]

    status_response = client.post(
        f"/defer/{defer_id}/status",
        json={
            "actor": "analyst_1",
            "status": "under_investigation",
            "note": "Opened for analyst review.",
        },
    )
    assert status_response.status_code == 200
    assert status_response.json()["new_status"] == "under_investigation"

    note_response = client.post(
        f"/defer/{defer_id}/notes",
        json={
            "actor": "analyst_1",
            "note": "Linked to repeated high-risk expense inflation pattern.",
        },
    )
    assert note_response.status_code == 200
    assert note_response.json()["note_count"] == 2

    release_response = client.post(
        f"/defer/{defer_id}/status",
        json={
            "actor": "analyst_1",
            "status": "released",
            "resolution_reason": "false_positive_after_manual_review",
        },
    )
    assert release_response.status_code == 200
    assert release_response.json()["resolution_reason"] == "false_positive_after_manual_review"

    summary_response = client.get("/defer/summaries/list")
    assert summary_response.status_code == 200
    summary = summary_response.json()["cases"][0]
    assert summary["status"] == "released"
    assert summary["resolution_reason"] == "false_positive_after_manual_review"
    assert summary["analyst_note_count"] == 2
