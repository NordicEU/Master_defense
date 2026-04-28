from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FindingSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnalysisFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    finding_type: str
    source_component: str
    severity: FindingSeverity
    score: float = Field(ge=0.0, le=1.0)
    message: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    rule_id: Optional[str] = None
