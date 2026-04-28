from shared.models.decision import DecisionAction, DecisionResult
from shared.models.risk import RiskAssessment
from shared.policies.quarantine_policy import build_quarantine_policy_result


def make_risk(
    total_score: float,
    rule_score: float = 0.0,
    statistical_score: float = 0.0,
    context_score: float = 0.0,
    semantic_score: float = 0.0,
):
    return RiskAssessment(
        rule_score=rule_score,
        statistical_score=statistical_score,
        context_score=context_score,
        semantic_score=semantic_score,
        total_score=total_score,
        confidence=0.84,
        findings=[],
        semantic_reasoning="test",
    )


def make_decision(action: DecisionAction) -> DecisionResult:
    return DecisionResult(
        action=action,
        policy_version="test_policy",
        reasons=["test_reason"],
    )


def test_quarantine_policy_quarantine_case():
    risk = make_risk(
        total_score=0.72,
        rule_score=0.35,
        statistical_score=0.30,
        context_score=0.82,
        semantic_score=0.10,
    )
    decision = make_decision(DecisionAction.QUARANTINE)

    result = build_quarantine_policy_result(risk, decision)

    assert result["severity"].value == "HIGH"
    assert result["isolation_mode"].value == "FULL_CONTAINMENT"
    assert result["initial_state"].value == "ISOLATED"
    assert result["release_eligible"] is False
    assert result["escalation_eligible"] is True


def test_quarantine_policy_review_case():
    risk = make_risk(
        total_score=0.42,
        rule_score=0.10,
        statistical_score=0.25,
        context_score=0.20,
        semantic_score=0.10,
    )
    decision = make_decision(DecisionAction.REVIEW)

    result = build_quarantine_policy_result(risk, decision)

    assert result["severity"].value == "MEDIUM"
    assert result["isolation_mode"].value in {"OBSERVE_ONLY", "RESTRICTED_EXECUTION"}
    assert result["initial_state"].value == "UNDER_REVIEW"
    assert result["escalation_eligible"] is False


def test_quarantine_policy_defer_case():
    risk = make_risk(
        total_score=0.18,
        rule_score=0.05,
        statistical_score=0.10,
        context_score=0.10,
        semantic_score=0.05,
    )
    decision = make_decision(DecisionAction.DEFER)

    result = build_quarantine_policy_result(risk, decision)

    assert result["severity"].value == "LOW"
    assert result["isolation_mode"].value == "OBSERVE_ONLY"
    assert result["initial_state"].value == "RETAINED"
    assert result["release_eligible"] is True
    assert result["escalation_eligible"] is False


def test_quarantine_policy_snapshot_contains_scores():
    risk = make_risk(
        total_score=0.52,
        rule_score=0.35,
        statistical_score=0.30,
        context_score=0.40,
        semantic_score=0.12,
    )
    decision = make_decision(DecisionAction.QUARANTINE)

    result = build_quarantine_policy_result(risk, decision)
    snapshot = result["decision_snapshot"]

    assert snapshot.risk_score == 0.52
    assert snapshot.rule_score == 0.35
    assert snapshot.statistical_score == 0.30
    assert snapshot.context_score == 0.40
    assert snapshot.semantic_score == 0.12
    assert snapshot.action == "QUARANTINE"
