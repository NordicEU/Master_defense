from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from services.defer_service import app as minefield_module


client = TestClient(minefield_module.app)


def setup_minefield_dir(tmp_path: Path) -> None:
    minefield_dir = tmp_path / "defer_cases"
    minefield_dir.mkdir(parents=True, exist_ok=True)
    minefield_module.MINEFIELD_DIR = minefield_dir


def make_payload(
    submission_id: str,
    person_id: str = "12345678901",
    employer_id: str = "999888777",
    risk_score: float = 0.93,
) -> dict:
    return {
        "submission": {
            "submission_id": submission_id,
            "source": "pytest",
        },
        "normalized_payload": {
            "person_id": person_id,
            "employer_id": employer_id,
            "declared_income": 50000,
            "declared_expenses": 950000,
        },
        "risk_assessment": {
            "total_score": risk_score,
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
        "agent_reasoning": "Extreme risk score and hostile financial indicators.",
        "agent_details": {
            "analysis_trace": {
                "rule_engine": {"rule_score": risk_score},
            }
        },
    }


def create_case(payload: dict) -> dict:
    response = client.post("/defer", json=payload)
    assert response.status_code == 200
    return response.json()


def test_repeated_subject_creates_behavior_capture_and_link_analysis(tmp_path: Path) -> None:
    setup_minefield_dir(tmp_path)

    first = create_case(make_payload("submission-001"))
    second = create_case(make_payload("submission-002"))

    stored = minefield_module.load_case(second["defer_id"])
    controls = stored["minefield_controls"]

    assert controls["behavior_capture"]["prior_same_subject_cases"] == 1
    assert controls["behavior_capture"]["prior_same_employer_cases"] == 1
    assert first["defer_id"] in controls["behavior_capture"]["recent_related_case_ids"]
    assert controls["link_analysis"]["related_case_count"] == 1
    assert controls["link_analysis"]["relation_counts"]["same_subject_id"] == 1
    assert controls["link_analysis"]["relation_counts"]["same_employer_id"] == 1


def test_progressive_delay_increases_for_repeated_high_risk_subject(tmp_path: Path) -> None:
    setup_minefield_dir(tmp_path)

    first = create_case(make_payload("submission-001"))
    second = create_case(make_payload("submission-002"))

    first_delay = minefield_module.load_case(first["defer_id"])["minefield_controls"]["progressive_delay"]
    second_delay = minefield_module.load_case(second["defer_id"])["minefield_controls"]["progressive_delay"]

    assert first_delay["enabled"] is True
    assert first_delay["recommended_delay_seconds"] == 20
    assert second_delay["enabled"] is True
    assert second_delay["recommended_delay_seconds"] > first_delay["recommended_delay_seconds"]
    assert "repeat_subject_activity" in second_delay["reasons"]


def test_trace_results_are_persisted_with_analyst_note(tmp_path: Path) -> None:
    setup_minefield_dir(tmp_path)

    created = create_case(make_payload("submission-001"))
    defer_id = created["defer_id"]

    response = client.post(
        f"/defer/{defer_id}/trace-results",
        json={
            "actor": "analyst_1",
            "target": "12345678901",
            "command": "manual-review-trace",
            "stdout": "linked high-risk pattern observed",
            "stderr": "",
            "returncode": 0,
        },
    )

    assert response.status_code == 200
    assert response.json()["trace_run_count"] == 1

    stored = minefield_module.load_case(defer_id)
    assert stored["trace_runs"][0]["target"] == "12345678901"
    assert stored["trace_runs"][0]["command"] == "manual-review-trace"
    assert stored["analyst_notes"][-1]["event"] == "trace_run"


def test_minefield_case_preserves_gateway_evidence(tmp_path: Path) -> None:
    setup_minefield_dir(tmp_path)

    created = create_case(make_payload("submission-001"))
    stored = minefield_module.load_case(created["defer_id"])

    assert stored["submission"]["submission_id"] == "submission-001"
    assert stored["risk_assessment"]["total_score"] == 0.93
    assert stored["decision_result"]["action"] == "MINEFIELD"
    assert stored["agent_reasoning"]
    assert stored["agent_details"]["analysis_trace"]["rule_engine"]["rule_score"] == 0.93
    assert stored["minefield_controls"]["behavior_capture"]["enabled"] is True
    assert stored["minefield_controls"]["link_analysis"]["enabled"] is True
