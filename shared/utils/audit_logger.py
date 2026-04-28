from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from shared.models.quarantine_case import AuditEvent, QuarantineCase
from shared.utils.runtime_paths import AUDIT_LOG_DIR


QUARANTINE_AUDIT_PATH = AUDIT_LOG_DIR / "quarantine_audit.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_audit_event(
    event_type: str,
    actor: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    return AuditEvent(
        event_type=event_type,
        actor=actor,
        message=message,
        details=details or {},
    )


def append_case_audit_event(
    case: QuarantineCase,
    event: AuditEvent,
) -> QuarantineCase:
    case.audit_trail.append(event)
    case.updated_at = event.timestamp
    return case


def write_quarantine_audit_log(
    case_id: str,
    submission_id: str,
    event: AuditEvent,
    risk_score: float | None = None,
    decision: str | None = None,
) -> None:
    record = {
        "timestamp": event.timestamp.isoformat(),
        "event_id": event.event_id,
        "event_type": event.event_type,
        "actor": event.actor,
        "message": event.message,
        "details": event.details,
        "case_id": case_id,
        "submission_id": submission_id,
        "risk_score": risk_score,
        "decision": decision,
        "logged_at": utc_now_iso(),
    }

    QUARANTINE_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with QUARANTINE_AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
