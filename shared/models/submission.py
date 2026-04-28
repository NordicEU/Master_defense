from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SubmissionPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


class Submission(BaseModel):
    submission_id: str = Field(default_factory=lambda: str(uuid4()))
    source: str = Field(default="web_form")
    payload_type: str = Field(default="tax_declaration")
    received_at: datetime = Field(default_factory=utc_now)
    correlation_id: Optional[str] = None
    schema_version: str = Field(default="v1")
    payload: SubmissionPayload = Field(default_factory=SubmissionPayload)
