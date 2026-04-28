from __future__ import annotations

import json
from pathlib import Path

from shared.models.decision import DecisionAction, DecisionResult
from shared.models.quarantine_case import DecisionSnapshot, QuarantineCase
from shared.models.risk import RiskAssessment
from shared.models.submission import Submission
from shared.utils import audit_logger


def build_case() -> QuarantineCase:
    submission = Submission()

    risk = RiskAssessment(
        rule_score=0.35,
        statistical_score=0.30,
        context_score=0.82,
        semantic_score=0.10,
        total_score=0.52,
        confidence=0.84,
        findings=[],
        semantic_reasoning="Semantic layer did not override containment.",
    )

    decision = DecisionResult(
        action=DecisionAction.QUARANTINE,
        policy_version="test_policy",
        reasons=["context_mismatch", "policy_containment"],
    )

    snapshot = DecisionSnapshot(
        action="QUARANTINE",
        risk_score=0.52,
        rule_score=0.35,
        statistical_score=0.30,
        context_score=0.82,
        semantic_score=0.10,
        reasons=["context_mismatch", "policy_containment"],
        semantic_reasoning="Semantic layer did not override containment.",
        policy_version="test_policy",
    )

    return QuarantineCase(
        submission=submission,
        normalized_payload={"document_type": "SKATTEPLIKT_2025"},
        risk_assessment=risk,
        decision_result=decision,
        decision_snapshot=snapshot,
    )


def test_create_audit_event():
    event = audit_logger.create_audit_event(
        event_type="CASE_CREATED",
        actor="quarantine_service",
        message="Case created.",
        details={"state": "ISOLATED"},
    )

    assert event.event_type == "CASE_CREATED"
    assert event.actor == "quarantine_service"
    assert event.message == "Case created."
    assert event.details["state"] == "ISOLATED"


def test_append_case_audit_event():
    case = build_case()
    original_updated_at = case.updated_at

    event = audit_logger.create_audit_event(
        event_type="CASE_CREATED",
        actor="quarantine_service",
        message="Case created.",
    )

    audit_logger.append_case_audit_event(case, event)

    assert len(case.audit_trail) == 1
    assert case.audit_trail[0].event_type == "CASE_CREATED"
    assert case.updated_at >= original_updated_at


def test_write_quarantine_audit_log(tmp_path):
    log_path = tmp_path / "quarantine_audit.jsonl"

    # monkeypatch module-level path
    audit_logger.QUARANTINE_AUDIT_PATH = log_path

    case = build_case()
    event = audit_logger.create_audit_event(
        event_type="CASE_CREATED",
        actor="quarantine_service",
        message="Case created.",
    )

    audit_logger.write_quarantine_audit_log(
        case_id=case.case_id,
        submission_id=case.submission.submission_id,
        event=event,
        risk_score=case.risk_assessment.total_score,
        decision=case.decision_result.action.value,
    )

    assert log_path.exists()

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["event_type"] == "CASE_CREATED"
    assert record["actor"] == "quarantine_service"
    assert record["case_id"] == case.case_id
    assert record["submission_id"] == case.submission.submission_id
    assert record["decision"] == "QUARANTINE"
