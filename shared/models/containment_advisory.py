from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AdvisoryHandoff(str, Enum):
    HOLD = "HOLD"
    NEEDS_HUMAN_OVERSIGHT = "NEEDS_HUMAN_OVERSIGHT"
    TRANSFER_TO_MINEFIELD = "TRANSFER_TO_MINEFIELD"
    RELEASE = "RELEASE"


class ContainmentAdvisory(BaseModel):
    advisory_id: str = Field(default_factory=lambda: str(uuid4()))
    recommended_handoff: AdvisoryHandoff
    recommended_target: Optional[str] = None
    confidence: float = 0.0
    reasoning: str
    risk_narrative: str
    should_require_human: bool = False
    generated_at: datetime = Field(default_factory=utc_now)
