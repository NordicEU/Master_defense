from __future__ import annotations

from shared.models.decision import DefenseAction
from shared.models.risk import RiskAssessment
from shared.policies.decision_policy import build_decision_result


def make_risk(total_score: float, findings: list[str]) -> RiskAssessment:
    return RiskAssessment(
        assessment_id="test-assessment",
        total_score=total_score,
        confidence=0.92,
        findings=findings,
        semantic_reasoning=" ".join(findings),
        recommended_action="CONTAIN",
    )


def test_extreme_risk_with_minefield_signal_routes_to_minefield() -> None:
    decision = build_decision_result(
        make_risk(
            total_score=0.93,
            findings=["extreme_expense_income_ratio"],
        )
    )

    assert decision.action == DefenseAction.MINEFIELD
    assert "minefield_threshold_met" in decision.reasons


def test_multiple_hostile_indicators_route_to_minefield_at_lower_threshold() -> None:
    decision = build_decision_result(
        make_risk(
            total_score=0.86,
            findings=[
                "extreme_expense_income_ratio",
                "severe_income_expense_mismatch",
            ],
        )
    )

    assert decision.action == DefenseAction.MINEFIELD
    assert "multiple_hostile_indicators_detected" in decision.reasons


def test_high_but_non_extreme_suspicious_case_does_not_route_to_minefield() -> None:
    decision = build_decision_result(
        make_risk(
            total_score=0.70,
            findings=["high_expense_income_ratio"],
        )
    )

    assert decision.action != DefenseAction.MINEFIELD


def test_minefield_boundary_requires_threshold_for_multiple_hostile_indicators() -> None:
    decision = build_decision_result(
        make_risk(
            total_score=0.85,
            findings=[
                "extreme_expense_income_ratio",
                "severe_income_expense_mismatch",
            ],
        )
    )

    assert decision.action != DefenseAction.MINEFIELD
