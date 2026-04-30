from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Minefield Service", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parents[2]
MINEFIELD_DIR = BASE_DIR / "runtime" / "defer_cases"
MINEFIELD_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def minefield_case_path(defer_id: str) -> Path:
    return MINEFIELD_DIR / f"{defer_id}.json"


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_case(defer_id: str) -> Dict[str, Any]:
    path = minefield_case_path(defer_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Minefield case not found.")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load minefield case: {exc}")


def case_summary(case: Dict[str, Any]) -> Dict[str, Any]:
    submission = case.get("submission", {})
    risk_assessment = case.get("risk_assessment", {})
    normalized_payload = case.get("normalized_payload", {})
    minefield_controls = case.get("minefield_controls", {})
    analyst_notes = case.get("analyst_notes", [])

    return {
        "defer_id": case.get("defer_id"),
        "submission_id": submission.get("submission_id", "unknown"),
        "subject_id": normalized_payload.get("person_id"),
        "source_agent": case.get("source_agent", "unknown"),
        "status": case.get("status", "queued"),
        "risk_score": risk_assessment.get("total_score"),
        "recommended_action": risk_assessment.get("recommended_action"),
        "received_at": case.get("received_at"),
        "updated_at": case.get("updated_at"),
        "resolution_reason": case.get("resolution_reason"),
        "analyst_note_count": len(analyst_notes) if isinstance(analyst_notes, list) else 0,
        "progressive_delay_enabled": bool(minefield_controls.get("progressive_delay", {}).get("enabled")),
        "behavior_capture_enabled": bool(minefield_controls.get("behavior_capture", {}).get("enabled")),
        "link_analysis_enabled": bool(minefield_controls.get("link_analysis", {}).get("enabled")),
        "auto_blacklist_enabled": bool(minefield_controls.get("auto_blacklist", {}).get("enabled")),
    }


class MinefieldStatus(str, Enum):
    QUEUED = "queued"
    UNDER_INVESTIGATION = "under_investigation"
    CONFIRMED_HOSTILE = "confirmed_hostile"
    RELEASED = "released"


class MinefieldRequest(BaseModel):
    submission: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    decision_result: Dict[str, Any] = Field(default_factory=dict)
    source_agent: str = "gateway"
    agent_reasoning: str | None = None
    agent_details: Dict[str, Any] = Field(default_factory=dict)
    containment_context: Dict[str, Any] = Field(default_factory=dict)


class MinefieldStatusUpdateRequest(BaseModel):
    actor: str = "minefield_operator"
    status: MinefieldStatus
    note: str | None = None
    resolution_reason: str | None = None


class MinefieldNoteRequest(BaseModel):
    actor: str = "minefield_operator"
    note: str


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "defer_service"}


@app.post("/defer")
def defer_case(request: MinefieldRequest) -> Dict[str, Any]:
    submission = request.submission or {}
    normalized_payload = request.normalized_payload or {}

    if not submission:
        raise HTTPException(status_code=400, detail="Missing submission payload.")

    defer_id = str(uuid4())
    received_at = utc_now_iso()
    record = {
        "defer_id": defer_id,
        "status": MinefieldStatus.QUEUED.value,
        "received_at": received_at,
        "updated_at": received_at,
        "submission": submission,
        "normalized_payload": normalized_payload,
        "risk_assessment": request.risk_assessment or {},
        "decision_result": request.decision_result or {},
        "source_agent": request.source_agent,
        "agent_reasoning": request.agent_reasoning,
        "agent_details": request.agent_details or {},
        "containment_context": request.containment_context or {},
        "resolution_reason": None,
        "analyst_notes": [],
        "minefield_notes": {
            "routing_reason": "Escalated for higher-friction handling and forensic review.",
            "subject_id": normalized_payload.get("person_id"),
            "employer_id": normalized_payload.get("employer_id"),
        },
        "minefield_controls": {
            "progressive_delay": {
                "enabled": False,
                "status": "placeholder",
                "notes": "Reserved for staged delay, throttling, or response slow-down under suspicious persistence.",
                "suggested_next_step": "Add delay tiers keyed by repeat attempts, risk score, or subject state.",
            },
            "behavior_capture": {
                "enabled": False,
                "status": "placeholder",
                "notes": "Reserved for capture of timing, retry patterns, field mutation behavior, and agent fingerprints.",
                "suggested_next_step": "Persist repeated-attempt telemetry and replay indicators for analyst review.",
            },
            "link_analysis": {
                "enabled": False,
                "status": "placeholder",
                "notes": "Reserved for correlating subject_id, employer_id, network source, and related case clusters.",
                "suggested_next_step": "Build case-link graph from repeated identifiers and suspicious co-occurrence patterns.",
            },
            "auto_blacklist": {
                "enabled": False,
                "status": "placeholder",
                "notes": "Reserved for controlled blocklist activation, network tracing hooks, or defensive response scripts.",
                "suggested_next_step": "Gate any automated blacklist or tracing action behind explicit policy thresholds and audit logging.",
                "safety_constraints": [
                    "manual_review_recommended",
                    "audit_required",
                    "threshold_based_activation",
                ],
            },
        },
    }

    write_json(minefield_case_path(defer_id), record)

    return {
        "message": "Submission accepted into minefield.",
        "defer_id": defer_id,
        "status": record["status"],
        "submission_id": submission.get("submission_id", "unknown"),
        "received_at": received_at,
    }


@app.get("/defer")
def list_deferred_cases() -> Dict[str, List[Dict[str, Any]]]:
    cases: List[Dict[str, Any]] = []

    for path in sorted(MINEFIELD_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            cases.append(data)

    return {"cases": cases}


@app.get("/defer/summaries/list")
def list_deferred_case_summaries() -> Dict[str, List[Dict[str, Any]]]:
    summaries: List[Dict[str, Any]] = []

    for path in sorted(MINEFIELD_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            summaries.append(case_summary(data))

    return {"cases": summaries}


@app.get("/defer/{defer_id}")
def get_deferred_case(defer_id: str) -> Dict[str, Any]:
    return load_case(defer_id)


@app.post("/defer/{defer_id}/status")
def update_deferred_case_status(defer_id: str, request: MinefieldStatusUpdateRequest) -> Dict[str, Any]:
    case = load_case(defer_id)
    old_status = str(case.get("status", MinefieldStatus.QUEUED.value))
    now = utc_now_iso()

    case["status"] = request.status.value
    case["updated_at"] = now

    if request.status == MinefieldStatus.RELEASED:
        case["resolution_reason"] = request.resolution_reason or "released_after_review"
    elif request.status == MinefieldStatus.CONFIRMED_HOSTILE:
        case["resolution_reason"] = request.resolution_reason or "confirmed_hostile_after_review"
    elif request.resolution_reason:
        case["resolution_reason"] = request.resolution_reason

    notes = case.get("analyst_notes", [])
    if not isinstance(notes, list):
        notes = []
    if request.note:
        notes.append(
            {
                "timestamp": now,
                "actor": request.actor,
                "note": request.note,
                "event": "status_update",
                "old_status": old_status,
                "new_status": request.status.value,
            }
        )
    case["analyst_notes"] = notes

    write_json(minefield_case_path(defer_id), case)

    return {
        "message": "Minefield case status updated.",
        "defer_id": defer_id,
        "old_status": old_status,
        "new_status": case["status"],
        "resolution_reason": case.get("resolution_reason"),
    }


@app.post("/defer/{defer_id}/notes")
def add_deferred_case_note(defer_id: str, request: MinefieldNoteRequest) -> Dict[str, Any]:
    case = load_case(defer_id)
    now = utc_now_iso()

    notes = case.get("analyst_notes", [])
    if not isinstance(notes, list):
        notes = []

    notes.append(
        {
            "timestamp": now,
            "actor": request.actor,
            "note": request.note,
            "event": "analyst_note",
        }
    )
    case["analyst_notes"] = notes
    case["updated_at"] = now

    write_json(minefield_case_path(defer_id), case)

    return {
        "message": "Minefield note added.",
        "defer_id": defer_id,
        "note_count": len(notes),
    }
