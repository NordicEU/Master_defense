from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


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


class DecisionResult(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    action: DefenseAction
    handoff: DefenseHandoff = DefenseHandoff.NONE
    policy_version: str = "v4_master"
    reasons: List[str] = Field(default_factory=list)
    confidence_label: Optional[str] = None
    decided_at: datetime = Field(default_factory=utc_now)
