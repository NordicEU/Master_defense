from __future__ import annotations

from typing import Optional

from shared.models.containment_advisory import (
    AdvisoryHandoff,
    ContainmentAdvisory,
)
from shared.models.quarantine_case import QuarantineCase, QuarantineState


def _risk_score(case: QuarantineCase) -> float:
    try:
        return float(case.risk_assessment.get("total_score", 0.0) or 0.0)
    except Exception:
        return 0.0


def _semantic_reasoning(case: QuarantineCase) -> str:
    return str(case.risk_assessment.get("semantic_reasoning", "") or "")


def _current_state(case: QuarantineCase) -> str:
    return case.current_state.value


def build_case_summary(case: QuarantineCase) -> str:
    return (
        f"state={case.current_state.value}, "
        f"severity={case.severity.value}, "
        f"isolation_mode={case.isolation_mode.value}, "
        f"risk_score={_risk_score(case):.2f}, "
        f"submission_id={case.submission.get('submission_id', 'unknown')}"
    )


def advisory_engine(case: QuarantineCase) -> ContainmentAdvisory:
    """
    LLM-style containment advisor.

    This is currently a deterministic stub that mimics how a real LLM-backed
    advisor should behave:
    - read containment state
    - read risk signals
    - produce a recommended handoff
    - provide confidence + reasoning + narrative

    Later, this function can be replaced or extended with an actual Llama/Ollama call.
    """
    total_score = _risk_score(case)
    semantic_reasoning = _semantic_reasoning(case)
    state = case.current_state

    # Terminal states: do not recommend active state changes.
    if state in {QuarantineState.RELEASED, QuarantineState.TRANSFERRED, QuarantineState.CLOSED}:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.NEEDS_HUMAN_OVERSIGHT,
            confidence=0.60,
            reasoning="Case is already in a terminal or near-terminal state; automatic containment action should not continue without operator intent.",
            risk_narrative=f"Containment state {_current_state(case)} is terminal or externally resolved.",
            should_require_human=True,
        )

    # Extremely high risk -> minefield transfer candidate
    if total_score >= 0.90:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.TRANSFER_TO_MINEFIELD,
            recommended_target="MINEFIELD",
            confidence=0.95,
            reasoning="Risk is extreme. The case should leave containment and enter the highest-friction response zone.",
            risk_narrative=f"Containment state {_current_state(case)} with very high risk score {total_score:.2f}.",
            should_require_human=False,
        )

    # Very high risk -> escalate containment severity
    if total_score >= 0.80:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.ESCALATE,
            confidence=0.88,
            reasoning="Case remains highly suspicious and should stay in containment under escalated handling.",
            risk_narrative=f"Containment state {_current_state(case)} with high risk score {total_score:.2f}.",
            should_require_human=False,
        )

    # Suspicious but not extreme -> retain
    if total_score >= 0.55:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.RETAIN,
            confidence=0.80,
            reasoning="Case should remain contained for deeper analysis before any downstream transfer or release.",
            risk_narrative=f"Containment state {_current_state(case)} with moderate-to-high risk score {total_score:.2f}.",
            should_require_human=False,
        )

    # Strong semantic indication of false positive / benign pattern -> release
    if "false positive" in semantic_reasoning.lower() or total_score < 0.25:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.RELEASE,
            confidence=0.78,
            reasoning="Case appears acceptable for release from containment.",
            risk_narrative=f"Containment state {_current_state(case)} with low effective risk score {total_score:.2f}.",
            should_require_human=False,
        )

    # Ambiguous -> human oversight
    return ContainmentAdvisory(
        recommended_handoff=AdvisoryHandoff.NEEDS_HUMAN_OVERSIGHT,
        confidence=0.62,
        reasoning="Case is ambiguous and requires human oversight before a final containment decision.",
        risk_narrative=f"Containment state {_current_state(case)} with ambiguous semantic pattern and risk score {total_score:.2f}.",
        should_require_human=True,
    )


def recommended_target(advisory: ContainmentAdvisory) -> Optional[str]:
    return advisory.recommended_target
