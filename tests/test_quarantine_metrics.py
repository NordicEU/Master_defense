from __future__ import annotations

from shared.models.decision import DecisionAction, DecisionResult
from shared.models.quarantine_case import (
    AuditEvent,
    CaseSeverity,
    DecisionSnapshot,
    IsolationMode,
    Observation,
    QuarantineCase,
    QuarantineState,
)
from shared.models.risk import RiskAssessment
from shared.models.submission import Submission
from services.quarantine_service.metrics import (
    build_quarantine_metrics,
    render_prometheus_metrics,
)


def build_case(
    state: QuarantineState,
    severity: CaseSeverity,
    isolation_mode: IsolationMode,
    release_eligible: bool = False,
    escalation_eligible: bool = False,
) -> QuarantineCase:
    submission = Submission()

    risk = RiskAssessment(
        rule_score=0.20,
        statistical_score=0.30,
        context_score=0.40,
        semantic_score=0.10,
        total_score=0.35,
        confidence=0.84,
        findings=[],
        semantic_reasoning="test",
    )

    decision = DecisionResult(
        action=DecisionAction.QUARANTINE,
        policy_version="test_policy",
        reasons=["test_reason"],
    )

    snapshot = DecisionSnapshot(
        action="QUARANTINE",
        risk_score=0.35,
        rule_score=0.20,
        statistical_score=0.30,
        context_score=0.40,
        semantic_score=0.10,
        reasons=["test_reason"],
        semantic_reasoning="test",
        policy_version="test_policy",
    )

    return QuarantineCase(
        submission=submission,
        normalized_payload={"document_type": "SKATTEPLIKT_2025"},
        risk_assessment=risk,
        decision_result=decision,
        current_state=state,
        isolation_mode=isolation_mode,
        severity=severity,
        decision_snapshot=snapshot,
        release_eligible=release_eligible,
        escalation_eligible=escalation_eligible,
        observations=[
            Observation(
                source="decision_service",
                kind="decision_snapshot",
                value={"action": "QUARANTINE"},
                confidence=0.84,
            )
        ],
        audit_trail=[
            AuditEvent(
                event_type="CASE_CREATED",
                actor="quarantine_service",
                message="Case created.",
            )
        ],
    )


def test_build_quarantine_metrics():
    cases = [
        build_case(
            state=QuarantineState.ISOLATED,
            severity=CaseSeverity.HIGH,
            isolation_mode=IsolationMode.FULL_CONTAINMENT,
            release_eligible=False,
            escalation_eligible=True,
        ),
        build_case(
            state=QuarantineState.UNDER_REVIEW,
            severity=CaseSeverity.MEDIUM,
            isolation_mode=IsolationMode.RESTRICTED_EXECUTION,
            release_eligible=True,
            escalation_eligible=False,
        ),
    ]

    metrics = build_quarantine_metrics(cases)

    assert metrics["total_cases"] == 2
    assert metrics["cases_by_state"]["ISOLATED"] == 1
    assert metrics["cases_by_state"]["UNDER_REVIEW"] == 1
    assert metrics["cases_by_severity"]["HIGH"] == 1
    assert metrics["cases_by_severity"]["MEDIUM"] == 1
    assert metrics["cases_by_isolation_mode"]["FULL_CONTAINMENT"] == 1
    assert metrics["cases_by_isolation_mode"]["RESTRICTED_EXECUTION"] == 1
    assert metrics["release_eligible_cases"] == 1
    assert metrics["escalation_eligible_cases"] == 1
    assert metrics["total_audit_events"] == 2
    assert metrics["total_observations"] == 2


def test_render_prometheus_metrics():
    cases = [
        build_case(
            state=QuarantineState.ISOLATED,
            severity=CaseSeverity.HIGH,
            isolation_mode=IsolationMode.FULL_CONTAINMENT,
            release_eligible=False,
            escalation_eligible=True,
        )
    ]

    metrics = build_quarantine_metrics(cases)
    rendered = render_prometheus_metrics(metrics)

    assert "quarantine_cases_total 1" in rendered
    assert 'quarantine_cases_by_state{state="ISOLATED"} 1' in rendered
    assert 'quarantine_cases_by_severity{severity="HIGH"} 1' in rendered
    assert 'quarantine_cases_by_isolation_mode{mode="FULL_CONTAINMENT"} 1' in rendered
    assert "quarantine_audit_events_total 1" in rendered
    assert "quarantine_observations_total 1" in rendered
