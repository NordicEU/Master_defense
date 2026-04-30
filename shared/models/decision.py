from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DefenseAction(str, Enum):
    ALLOW = "ALLOW"
    CONTAIN = "CONTAIN"
    DECEIVE = "DECEIVE"
    HONEYPOT = "HONEYPOT"
    MINEFIELD = "MINEFIELD"


class DefenseHandoff(str, Enum):
    NONE = "NONE"
    RELEASE = "RELEASE"
    RETAIN = "RETAIN"
    ESCALATE = "ESCALATE"
    NEEDS_HUMAN_OVERSIGHT = "NEEDS_HUMAN_OVERSIGHT"
    TRANSFER_TO_CONTAIN = "TRANSFER_TO_CONTAIN"
    TRANSFER_TO_MINEFIELD = "TRANSFER_TO_MINEFIELD"


class DecisionConfidenceLabel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DecisionResult(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    action: DefenseAction
    handoff: DefenseHandoff = DefenseHandoff.NONE
    policy_version: str = "v5_master"
    reasons: List[str] = Field(default_factory=list)
    confidence_label: Optional[DecisionConfidenceLabel] = None
    decided_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_action_handoff(self) -> "DecisionResult":
        allowed_handoffs = {
            DefenseAction.ALLOW: {DefenseHandoff.RELEASE},
            DefenseAction.CONTAIN: {
                DefenseHandoff.RETAIN,
                DefenseHandoff.NEEDS_HUMAN_OVERSIGHT,
                DefenseHandoff.TRANSFER_TO_CONTAIN,
            },
            DefenseAction.DECEIVE: {DefenseHandoff.NONE},
            DefenseAction.HONEYPOT: {DefenseHandoff.NONE},
            DefenseAction.MINEFIELD: {
                DefenseHandoff.ESCALATE,
                DefenseHandoff.TRANSFER_TO_MINEFIELD,
            },
        }

        valid_handoffs = allowed_handoffs.get(self.action, set())
        if self.handoff not in valid_handoffs:
            raise ValueError(f"Invalid handoff {self.handoff.value} for action {self.action.value}")

        if not self.reasons:
            raise ValueError("DecisionResult must include at least one reason.")

        return self
