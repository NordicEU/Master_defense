from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QuarantineState(str, Enum):
    CONTAINED = "CONTAINED"
    UNDER_REVIEW = "UNDER_REVIEW"
    TRANSFERRED = "TRANSFERRED"
    RELEASED = "RELEASED"
    CLOSED = "CLOSED"


class IsolationMode(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    RESTRICTED_EXECUTION = "RESTRICTED_EXECUTION"
    FULL_CONTAINMENT = "FULL_CONTAINMENT"


class CaseSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionSnapshot(BaseModel):
    action: str
    risk_score: float = 0.0
    rule_score: float = 0.0
    statistical_score: float = 0.0
    context_score: float = 0.0
    semantic_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    semantic_reasoning: Optional[str] = None
    policy_version: str = "v4_master"
    captured_at: datetime = Field(default_factory=utc_now)


class Observation(BaseModel):
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    kind: str
    value: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    actor: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class QuarantineCase(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    submission: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    decision_result: Dict[str, Any] = Field(default_factory=dict)

    subject_id: Optional[str] = None
    source_agent: str = "gateway"
    upstream_agent_reasoning: Optional[str] = None

    current_state: QuarantineState = QuarantineState.CONTAINED
    isolation_mode: IsolationMode = IsolationMode.RESTRICTED_EXECUTION
    severity: CaseSeverity = CaseSeverity.HIGH

    decision_snapshot: DecisionSnapshot

    observations: List[Observation] = Field(default_factory=list)
    audit_trail: List[AuditEvent] = Field(default_factory=list)

    release_eligible: bool = False
    transfer_eligible: bool = False
    requires_human_oversight: bool = False
    transfer_target: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
