from __future__ import annotations

from typing import Any, Dict

from shared.models.decision import DecisionResult
from shared.models.quarantine_case import (
    DecisionSnapshot,
    IsolationMode,
    QuarantineState,
)


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def build_quarantine_policy_result(
    risk_assessment: Dict[str, Any],
    decision_result: DecisionResult,
) -> Dict[str, Any]:
    total_score = _safe_float(risk_assessment.get("total_score"))
    confidence = _safe_float(risk_assessment.get("confidence"))

    if total_score >= 0.80:
        severity = "HIGH"
        isolation_mode = IsolationMode.RESTRICTED_EXECUTION
    elif total_score >= 0.55:
        severity = "MEDIUM"
        isolation_mode = IsolationMode.RESTRICTED_EXECUTION
    else:
        severity = "LOW"
        isolation_mode = IsolationMode.OBSERVATION_ONLY

    if confidence < 0.45 and total_score < 0.80:
        initial_state = QuarantineState.UNDER_REVIEW
        requires_human_oversight = True
    else:
        initial_state = QuarantineState.CONTAINED
        requires_human_oversight = False

    release_eligible = False
    transfer_eligible = total_score >= 0.90

    decision_snapshot = DecisionSnapshot(
        action=decision_result.action,
        handoff=decision_result.handoff,
        reasons=decision_result.reasons,
        policy_version=decision_result.policy_version,
        confidence_label=decision_result.confidence_label,
    )

    return {
        "initial_state": initial_state,
        "severity": severity,
        "isolation_mode": isolation_mode,
        "decision_snapshot": decision_snapshot,
        "release_eligible": release_eligible,
        "transfer_eligible": transfer_eligible,
        "requires_human_oversight": requires_human_oversight,
    }
