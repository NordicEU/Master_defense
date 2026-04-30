from __future__ import annotations

from shared.models.decision import DecisionResult, DefenseAction, DefenseHandoff
from shared.policies.quarantine_policy import build_quarantine_policy_result


def make_decision(action: DefenseAction, handoff: DefenseHandoff) -> DecisionResult:
    return DecisionResult(
        action=action,
        handoff=handoff,
        reasons=["test_reason"],
    )


def test_quarantine_policy_marks_high_risk_case_transfer_eligible() -> None:
    result = build_quarantine_policy_result(
        risk_assessment={
            "total_score": 0.93,
            "confidence": 0.91,
        },
        decision_result=make_decision(DefenseAction.MINEFIELD, DefenseHandoff.ESCALATE),
    )

    assert result["initial_state"].value == "CONTAINED"
    assert result["severity"] == "HIGH"
    assert result["transfer_eligible"] is True
    assert result["requires_human_oversight"] is False


def test_quarantine_policy_marks_low_confidence_case_under_review() -> None:
    result = build_quarantine_policy_result(
        risk_assessment={
            "total_score": 0.42,
            "confidence": 0.20,
        },
        decision_result=make_decision(DefenseAction.CONTAIN, DefenseHandoff.NEEDS_HUMAN_OVERSIGHT),
    )

    assert result["initial_state"].value == "UNDER_REVIEW"
    assert result["severity"] == "LOW"
    assert result["transfer_eligible"] is False
    assert result["requires_human_oversight"] is True
