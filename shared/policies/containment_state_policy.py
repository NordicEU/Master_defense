from __future__ import annotations

from shared.models.quarantine_case import QuarantineState


ALLOWED_TRANSITIONS = {
    QuarantineState.CONTAINED: {
        QuarantineState.CONTAINED,
        QuarantineState.UNDER_REVIEW,
        QuarantineState.RELEASED,
        QuarantineState.TRANSFERRED,
        QuarantineState.CLOSED,
    },
    QuarantineState.UNDER_REVIEW: {
        QuarantineState.UNDER_REVIEW,
        QuarantineState.CONTAINED,
        QuarantineState.RELEASED,
        QuarantineState.TRANSFERRED,
        QuarantineState.CLOSED,
    },
    QuarantineState.RELEASED: {
        QuarantineState.RELEASED,
        QuarantineState.CLOSED,
    },
    QuarantineState.TRANSFERRED: {
        QuarantineState.TRANSFERRED,
        QuarantineState.CLOSED,
    },
    QuarantineState.CLOSED: {
        QuarantineState.CLOSED,
    },
}


def assert_transition_allowed(current_state: QuarantineState, new_state: QuarantineState) -> None:
    allowed_targets = ALLOWED_TRANSITIONS.get(current_state, set())
    if new_state not in allowed_targets:
        raise ValueError(
            f"Illegal containment state transition: {current_state.value} -> {new_state.value}"
        )
