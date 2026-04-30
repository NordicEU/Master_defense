from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.models.decision import (
    DecisionConfidenceLabel,
    DecisionResult,
    DefenseAction,
    DefenseHandoff,
)


def test_decision_result_accepts_valid_action_handoff_pair() -> None:
    result = DecisionResult(
        action=DefenseAction.CONTAIN,
        handoff=DefenseHandoff.RETAIN,
        reasons=["suspicious_claim_contained"],
        confidence_label=DecisionConfidenceLabel.MEDIUM,
    )

    assert result.action == DefenseAction.CONTAIN
    assert result.handoff == DefenseHandoff.RETAIN
    assert result.policy_version == "v5_master"


def test_decision_result_rejects_invalid_action_handoff_pair() -> None:
    with pytest.raises(ValidationError):
        DecisionResult(
            action=DefenseAction.ALLOW,
            handoff=DefenseHandoff.ESCALATE,
            reasons=["bad_combo"],
        )


def test_decision_result_requires_reason() -> None:
    with pytest.raises(ValidationError):
        DecisionResult(
            action=DefenseAction.MINEFIELD,
            handoff=DefenseHandoff.ESCALATE,
            reasons=[],
        )
