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


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


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


def list_existing_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(MINEFIELD_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            cases.append(data)
    return cases


def build_behavior_capture(
    normalized_payload: Dict[str, Any],
    submission: Dict[str, Any],
    source_agent: str,
    risk_assessment: Dict[str, Any],
    existing_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    subject_id = _safe_str(normalized_payload.get("person_id"))
    employer_id = _safe_str(normalized_payload.get("employer_id"))
    risk_score = float(risk_assessment.get("total_score", 0.0) or 0.0)

    prior_same_subject = 0
    prior_same_employer = 0
    prior_same_pair = 0
    prior_same_source_agent = 0
    prior_high_risk = 0
    related_case_ids: List[str] = []

    for case in existing_cases:
        case_payload = case.get("normalized_payload", {})
        case_subject_id = _safe_str(case_payload.get("person_id"))
        case_employer_id = _safe_str(case_payload.get("employer_id"))
        case_source_agent = _safe_str(case.get("source_agent"))
        case_risk_score = float(case.get("risk_assessment", {}).get("total_score", 0.0) or 0.0)
        case_id = _safe_str(case.get("defer_id"))

        same_subject = subject_id and subject_id == case_subject_id
        same_employer = employer_id and employer_id == case_employer_id

        if same_subject:
            prior_same_subject += 1
        if same_employer:
            prior_same_employer += 1
        if same_subject and same_employer:
            prior_same_pair += 1
        if source_agent and source_agent == case_source_agent:
            prior_same_source_agent += 1
        if case_risk_score >= 0.86:
            prior_high_risk += 1

        if case_id and (same_subject or same_employer):
            related_case_ids.append(case_id)

    return {
        "enabled": True,
        "status": "active",
        "captured_at": utc_now_iso(),
        "subject_id": subject_id or None,
        "employer_id": employer_id or None,
        "source_agent": source_agent,
        "submission_source": _safe_str(submission.get("source")) or None,
        "generated_label": _safe_str(submission.get("generated_label")) or None,
        "risk_score": round(risk_score, 2),
        "prior_same_subject_cases": prior_same_subject,
        "prior_same_employer_cases": prior_same_employer,
        "prior_same_subject_employer_pair_cases": prior_same_pair,
        "prior_same_source_agent_cases": prior_same_source_agent,
        "prior_high_risk_minefield_cases": prior_high_risk,
        "recent_related_case_ids": related_case_ids[:5],
        "notes": "Initial behavioral snapshot captured at minefield intake.",
    }


def build_link_analysis(
    normalized_payload: Dict[str, Any],
    source_agent: str,
    existing_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    subject_id = _safe_str(normalized_payload.get("person_id"))
    employer_id = _safe_str(normalized_payload.get("employer_id"))

    related_cases: List[Dict[str, Any]] = []
    relation_counts = {
        "same_subject_id": 0,
        "same_employer_id": 0,
        "same_source_agent": 0,
    }

    for case in existing_cases:
        case_payload = case.get("normalized_payload", {})
        case_subject_id = _safe_str(case_payload.get("person_id"))
        case_employer_id = _safe_str(case_payload.get("employer_id"))
        case_source_agent = _safe_str(case.get("source_agent"))
        reasons: List[str] = []

        if subject_id and subject_id == case_subject_id:
            reasons.append("same_subject_id")
            relation_counts["same_subject_id"] += 1
        if employer_id and employer_id == case_employer_id:
            reasons.append("same_employer_id")
            relation_counts["same_employer_id"] += 1
        if source_agent and source_agent == case_source_agent:
            reasons.append("same_source_agent")
            relation_counts["same_source_agent"] += 1

        if reasons:
            related_cases.append(
                {
                    "defer_id": _safe_str(case.get("defer_id")) or "unknown",
                    "submission_id": _safe_str(case.get("submission", {}).get("submission_id")) or "unknown",
                    "status": _safe_str(case.get("status")) or "unknown",
                    "reasons": reasons,
                }
            )

    return {
        "enabled": True,
        "status": "active",
        "linked_at": utc_now_iso(),
        "subject_id": subject_id or None,
        "employer_id": employer_id or None,
        "source_agent": source_agent,
        "related_case_count": len(related_cases),
        "relation_counts": relation_counts,
        "related_cases": related_cases[:10],
        "notes": "Lightweight link analysis based on repeated identifiers and source-agent overlap.",
    }


def build_progressive_delay(
    normalized_payload: Dict[str, Any],
    risk_assessment: Dict[str, Any],
    existing_cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    subject_id = _safe_str(normalized_payload.get("person_id"))
    employer_id = _safe_str(normalized_payload.get("employer_id"))
    risk_score = float(risk_assessment.get("total_score", 0.0) or 0.0)

    repeated_subject = 0
    repeated_employer = 0

    for case in existing_cases:
        case_payload = case.get("normalized_payload", {})
        if subject_id and subject_id == _safe_str(case_payload.get("person_id")):
            repeated_subject += 1
        if employer_id and employer_id == _safe_str(case_payload.get("employer_id")):
            repeated_employer += 1

    recommended_delay_seconds = 0
    delay_tier = "none"
    reasons: List[str] = []

    if risk_score >= 0.90:
        recommended_delay_seconds += 20
        delay_tier = "high"
        reasons.append("extreme_risk_score")
    elif risk_score >= 0.80:
        recommended_delay_seconds += 10
        delay_tier = "medium"
        reasons.append("high_risk_score")
    elif risk_score >= 0.66:
        recommended_delay_seconds += 5
        delay_tier = "low"
        reasons.append("elevated_risk_score")

    if repeated_subject >= 1:
        recommended_delay_seconds += 10
        delay_tier = "high" if recommended_delay_seconds >= 20 else "medium"
        reasons.append("repeat_subject_activity")

    if repeated_employer >= 2:
        recommended_delay_seconds += 5
        if delay_tier == "none":
            delay_tier = "low"
        reasons.append("repeat_employer_activity")

    return {
        "enabled": recommended_delay_seconds > 0,
        "status": "active" if recommended_delay_seconds > 0 else "inactive",
        "evaluated_at": utc_now_iso(),
        "delay_tier": delay_tier,
        "recommended_delay_seconds": recommended_delay_seconds,
        "reasons": reasons,
        "subject_repeat_count": repeated_subject,
        "employer_repeat_count": repeated_employer,
        "notes": "Progressive delay is currently advisory metadata for operator-controlled friction.",
    }


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
        "request_ip": submission.get("request_ip"),
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


class MinefieldTraceResultRequest(BaseModel):
    actor: str = "minefield_operator"
    target: str
    command: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "defer_service"}


@app.post("/defer")
def defer_case(request: MinefieldRequest) -> Dict[str, Any]:
    submission = request.submission or {}
    normalized_payload = request.normalized_payload or {}

    if not submission:
        raise HTTPException(status_code=400, detail="Missing submission payload.")

    existing_cases = list_existing_cases()
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
        "trace_runs": [],
        "minefield_notes": {
            "routing_reason": "Escalated for higher-friction handling and forensic review.",
            "subject_id": normalized_payload.get("person_id"),
            "employer_id": normalized_payload.get("employer_id"),
        },
        "minefield_controls": {
            "progressive_delay": build_progressive_delay(
                normalized_payload=normalized_payload,
                risk_assessment=request.risk_assessment or {},
                existing_cases=existing_cases,
            ),
            "behavior_capture": build_behavior_capture(
                normalized_payload=normalized_payload,
                submission=submission,
                source_agent=request.source_agent,
                risk_assessment=request.risk_assessment or {},
                existing_cases=existing_cases,
            ),
            "link_analysis": build_link_analysis(
                normalized_payload=normalized_payload,
                source_agent=request.source_agent,
                existing_cases=existing_cases,
            ),
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


@app.post("/defer/{defer_id}/trace-results")
def add_trace_results(defer_id: str, request: MinefieldTraceResultRequest) -> Dict[str, Any]:
    case = load_case(defer_id)
    now = utc_now_iso()

    trace_runs = case.get("trace_runs", [])
    if not isinstance(trace_runs, list):
        trace_runs = []

    trace_runs.append(
        {
            "timestamp": now,
            "actor": request.actor,
            "target": request.target,
            "command": request.command,
            "stdout": request.stdout,
            "stderr": request.stderr,
            "returncode": request.returncode,
        }
    )
    case["trace_runs"] = trace_runs
    case["updated_at"] = now

    notes = case.get("analyst_notes", [])
    if not isinstance(notes, list):
        notes = []
    notes.append(
        {
            "timestamp": now,
            "actor": request.actor,
            "event": "trace_run",
            "note": f"Trace command executed against target {request.target}.",
        }
    )
    case["analyst_notes"] = notes

    write_json(minefield_case_path(defer_id), case)

    return {
        "message": "Trace results stored.",
        "defer_id": defer_id,
        "trace_run_count": len(trace_runs),
    }
