from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from services.quarantine_service.subject_control import (
    SubjectControlRegistry,
    SubjectControlState,
)
from shared.models.containment_advisory import (
    AdvisoryHandoff,
    ContainmentAdvisory,
)
from shared.models.decision import DecisionResult
from shared.models.quarantine_case import (
    AuditEvent,
    Observation,
    QuarantineCase,
    QuarantineState,
)
from shared.policies.containment_state_policy import assert_transition_allowed
from shared.policies.quarantine_policy import build_quarantine_policy_result
from shared.utils.runtime_paths import AUDIT_LOG_DIR, QUARANTINE_RUNTIME_DIR

app = FastAPI(title="Quarantine Service", version="8.0.0")

QUARANTINE_DIR = QUARANTINE_RUNTIME_DIR
AUDIT_PATH = AUDIT_LOG_DIR / "quarantine_audit.jsonl"
MINEFIELD_URL = os.getenv("MINEFIELD_URL", "http://127.0.0.1:8006/defer")

QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)

SUBJECT_CONTROL_DIR = QUARANTINE_DIR / "subject_control"
SUBJECT_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
subject_registry = SubjectControlRegistry(SUBJECT_CONTROL_DIR, lambda: utc_now())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def case_path(case_id: str) -> Path:
    return QUARANTINE_DIR / f"{case_id}.json"


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def append_audit_log(entry: Dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def load_case(case_id: str) -> QuarantineCase:
    path = case_path(case_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Quarantine case not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return QuarantineCase.model_validate(data)


def save_case(case: QuarantineCase) -> None:
    case.updated_at = utc_now()
    write_json(case_path(case.case_id), case.model_dump(mode="json"))


def create_audit_event(
    case: QuarantineCase,
    event_type: str,
    actor: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor=actor,
        message=message,
        details=details or {},
        timestamp=utc_now(),
    )
    case.audit_trail.append(event)

    append_audit_log(
        {
            "timestamp": event.timestamp.isoformat(),
            "event_id": event.event_id,
            "event_type": event.event_type,
            "actor": event.actor,
            "message": event.message,
            "details": event.details,
            "case_id": case.case_id,
            "submission_id": case.submission.get("submission_id"),
            "subject_id": case.subject_id,
            "risk_score": case.risk_assessment.get("total_score", 0.0),
            "decision": case.decision_snapshot.action,
            "logged_at": utc_now().isoformat(),
        }
    )
    return event


def create_observation(
    source: str,
    kind: str,
    value: Dict[str, Any],
    confidence: Optional[float] = None,
) -> Observation:
    return Observation(
        source=source,
        kind=kind,
        value=value,
        confidence=confidence,
        timestamp=utc_now(),
    )


def case_summary(case: QuarantineCase) -> Dict[str, Any]:
    return {
        "case_id": case.case_id,
        "submission_id": case.submission.get("submission_id", "unknown"),
        "subject_id": case.subject_id,
        "source_agent": case.source_agent,
        "status": case.current_state.value,
        "severity": case.severity.value,
        "isolation_mode": case.isolation_mode.value,
        "risk_score": case.risk_assessment.get("total_score", 0.0),
        "decision": case.decision_snapshot.action,
        "release_eligible": case.release_eligible,
        "transfer_eligible": case.transfer_eligible,
        "requires_human_oversight": case.requires_human_oversight,
        "transfer_target": case.transfer_target,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }


def advisory_engine(case: QuarantineCase) -> ContainmentAdvisory:
    total_score = float(case.risk_assessment.get("total_score", 0.0) or 0.0)
    source_agent = case.source_agent

    if case.current_state in {
        QuarantineState.TRANSFERRED,
        QuarantineState.RELEASED,
        QuarantineState.CLOSED,
    }:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.NEEDS_HUMAN_OVERSIGHT,
            confidence=0.60,
            reasoning="Case is already terminal or externally resolved; no automatic action should continue.",
            risk_narrative=f"Containment state {case.current_state.value} is terminal or externally resolved.",
            should_require_human=True,
        )

    if total_score >= 0.90:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.TRANSFER_TO_MINEFIELD,
            recommended_target="MINEFIELD",
            confidence=0.95,
            reasoning="Risk is extreme. Case should be moved from containment to minefield.",
            risk_narrative=f"Contained case has very high risk score {total_score:.2f}.",
            should_require_human=False,
        )

    if source_agent in {"honeypot", "deceiver"} and total_score >= 0.70:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.NEEDS_HUMAN_OVERSIGHT,
            confidence=0.84,
            reasoning="Agent-forwarded suspicious case should remain contained under human oversight.",
            risk_narrative=f"Agent-forwarded case from {source_agent} with risk score {total_score:.2f}.",
            should_require_human=True,
        )

    if total_score >= 0.55:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.HOLD,
            confidence=0.80,
            reasoning="Case should remain contained for further controlled handling.",
            risk_narrative=f"Contained case has moderate-to-high risk score {total_score:.2f}.",
            should_require_human=False,
        )

    if total_score < 0.25:
        return ContainmentAdvisory(
            recommended_handoff=AdvisoryHandoff.RELEASE,
            confidence=0.76,
            reasoning="Case appears low-risk enough for controlled release.",
            risk_narrative=f"Contained case has low effective risk score {total_score:.2f}.",
            should_require_human=False,
        )

    return ContainmentAdvisory(
        recommended_handoff=AdvisoryHandoff.NEEDS_HUMAN_OVERSIGHT,
        confidence=0.65,
        reasoning="Case is ambiguous and should remain contained pending human oversight.",
        risk_narrative=f"Contained case is ambiguous with risk score {total_score:.2f}.",
        should_require_human=True,
    )


def apply_state_transition(case: QuarantineCase, new_state: QuarantineState) -> None:
    assert_transition_allowed(case.current_state, new_state)
    case.current_state = new_state


def forward_to_minefield(case: QuarantineCase) -> Dict[str, Any]:
    payload = {
        "submission": case.submission,
        "normalized_payload": case.normalized_payload,
        "risk_assessment": case.risk_assessment,
        "decision_result": case.decision_result,
        "containment_context": {
            "case_id": case.case_id,
            "current_state": case.current_state.value,
            "severity": case.severity.value,
            "isolation_mode": case.isolation_mode.value,
            "decision_snapshot": case.decision_snapshot.model_dump(mode="json"),
            "source_agent": case.source_agent,
            "subject_id": case.subject_id,
        },
        "source_agent": "containment",
        "agent_reasoning": case.upstream_agent_reasoning,
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(MINEFIELD_URL, json=payload)
            response.raise_for_status()
            try:
                return {
                    "ok": True,
                    "target_url": MINEFIELD_URL,
                    "status_code": response.status_code,
                    "response_json": response.json(),
                }
            except Exception:
                return {
                    "ok": True,
                    "target_url": MINEFIELD_URL,
                    "status_code": response.status_code,
                    "response_text": response.text,
                }
    except Exception as exc:
        return {
            "ok": False,
            "target_url": MINEFIELD_URL,
            "error": str(exc),
        }


def metrics_snapshot() -> Dict[str, Any]:
    total_cases = 0
    cases_by_state: Dict[str, int] = {}
    cases_by_severity: Dict[str, int] = {}
    cases_by_isolation_mode: Dict[str, int] = {}
    release_eligible_cases = 0
    transfer_eligible_cases = 0
    human_oversight_cases = 0
    total_audit_events = 0
    total_observations = 0
    transferred_cases = 0
    released_cases = 0

    for path in sorted(QUARANTINE_DIR.glob("*.json")):
        try:
            case = QuarantineCase.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue

        total_cases += 1
        cases_by_state[case.current_state.value] = cases_by_state.get(case.current_state.value, 0) + 1
        cases_by_severity[case.severity.value] = cases_by_severity.get(case.severity.value, 0) + 1
        cases_by_isolation_mode[case.isolation_mode.value] = (
            cases_by_isolation_mode.get(case.isolation_mode.value, 0) + 1
        )

        if case.release_eligible:
            release_eligible_cases += 1
        if case.transfer_eligible:
            transfer_eligible_cases += 1
        if case.requires_human_oversight:
            human_oversight_cases += 1
        if case.current_state.value == "TRANSFERRED":
            transferred_cases += 1
        if case.current_state.value == "RELEASED":
            released_cases += 1

        total_audit_events += len(case.audit_trail)
        total_observations += len(case.observations)

    return {
        "total_cases": total_cases,
        "cases_by_state": cases_by_state,
        "cases_by_severity": cases_by_severity,
        "cases_by_isolation_mode": cases_by_isolation_mode,
        "release_eligible_cases": release_eligible_cases,
        "transfer_eligible_cases": transfer_eligible_cases,
        "human_oversight_cases": human_oversight_cases,
        "total_audit_events": total_audit_events,
        "total_observations": total_observations,
        "transferred_cases": transferred_cases,
        "released_cases": released_cases,
    }


def render_prometheus_metrics(snapshot: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append("# HELP quarantine_cases_total Total number of containment cases.")
    lines.append("# TYPE quarantine_cases_total gauge")
    lines.append(f"quarantine_cases_total {snapshot['total_cases']}")

    lines.append("# HELP quarantine_release_eligible_cases Total number of release-eligible containment cases.")
    lines.append("# TYPE quarantine_release_eligible_cases gauge")
    lines.append(f"quarantine_release_eligible_cases {snapshot['release_eligible_cases']}")

    lines.append("# HELP quarantine_transfer_eligible_cases Total number of transfer-eligible containment cases.")
    lines.append("# TYPE quarantine_transfer_eligible_cases gauge")
    lines.append(f"quarantine_transfer_eligible_cases {snapshot['transfer_eligible_cases']}")

    lines.append("# HELP containment_human_oversight_cases_total Total number of containment cases requiring human oversight.")
    lines.append("# TYPE containment_human_oversight_cases_total gauge")
    lines.append(f"containment_human_oversight_cases_total {snapshot['human_oversight_cases']}")

    lines.append("# HELP containment_transferred_cases_total Total number of transferred containment cases.")
    lines.append("# TYPE containment_transferred_cases_total gauge")
    lines.append(f"containment_transferred_cases_total {snapshot['transferred_cases']}")

    lines.append("# HELP containment_released_cases_total Total number of released containment cases.")
    lines.append("# TYPE containment_released_cases_total gauge")
    lines.append(f"containment_released_cases_total {snapshot['released_cases']}")

    lines.append("# HELP quarantine_audit_events_total Total number of audit events across containment cases.")
    lines.append("# TYPE quarantine_audit_events_total gauge")
    lines.append(f"quarantine_audit_events_total {snapshot['total_audit_events']}")

    lines.append("# HELP quarantine_observations_total Total number of observations across containment cases.")
    lines.append("# TYPE quarantine_observations_total gauge")
    lines.append(f"quarantine_observations_total {snapshot['total_observations']}")

    lines.append("# HELP quarantine_cases_by_state Number of containment cases by state.")
    lines.append("# TYPE quarantine_cases_by_state gauge")
    for state, count in sorted(snapshot["cases_by_state"].items()):
        lines.append(f'quarantine_cases_by_state{{state="{state}"}} {count}')

    lines.append("# HELP quarantine_cases_by_severity Number of containment cases by severity.")
    lines.append("# TYPE quarantine_cases_by_severity gauge")
    for severity, count in sorted(snapshot["cases_by_severity"].items()):
        lines.append(f'quarantine_cases_by_severity{{severity="{severity}"}} {count}')

    lines.append("# HELP quarantine_cases_by_isolation_mode Number of containment cases by isolation mode.")
    lines.append("# TYPE quarantine_cases_by_isolation_mode gauge")
    for mode, count in sorted(snapshot["cases_by_isolation_mode"].items()):
        lines.append(f'quarantine_cases_by_isolation_mode{{mode="{mode}"}} {count}')

    return "\n".join(lines) + "\n"


class QuarantineCreateRequest(BaseModel):
    submission: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    decision_result: Dict[str, Any] = Field(default_factory=dict)
    source_agent: str = "gateway"
    agent_reasoning: Optional[str] = None
    agent_confidence: Optional[float] = None
    agent_details: Dict[str, Any] = Field(default_factory=dict)


class CaseActionRequest(BaseModel):
    actor: str = "containment_operator"
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ApplyAdvisoryRequest(BaseModel):
    actor: str = "containment_policy"
    force_human_override: bool = False


class AdminCombinedResetRequest(BaseModel):
    actor: str = "admin_operator"
    reason: str = "manual combined reset"
    subject_id: str
    case_id: str


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "quarantine_service"}


@app.get("/subjects/{subject_id}")
def get_subject_control(subject_id: str) -> Dict[str, Any]:
    return subject_registry.get_or_default(subject_id)


@app.post("/subjects/upsert")
def subject_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    subject_id = str(payload.get("subject_id") or "").strip()
    state = str(payload.get("state") or "").strip().upper()
    reason = str(payload.get("reason") or "").strip()
    linked_case_id = payload.get("linked_case_id")

    if not subject_id:
        raise HTTPException(status_code=400, detail="Missing subject_id")

    if state not in {s.value for s in SubjectControlState}:
        raise HTTPException(status_code=400, detail=f"Invalid state: {state}")

    return subject_registry.upsert(
        subject_id=subject_id,
        state=SubjectControlState(state),
        reason=reason or "manual_update",
        linked_case_id=linked_case_id,
    )


@app.post("/admin/reset")
def admin_combined_reset(request: AdminCombinedResetRequest) -> Dict[str, Any]:
    case = load_case(request.case_id)
    old_state = case.current_state.value

    if case.current_state not in {QuarantineState.RELEASED, QuarantineState.CLOSED}:
        try:
            apply_state_transition(case, QuarantineState.RELEASED)
        except Exception:
            case.current_state = QuarantineState.RELEASED

    case.release_eligible = False
    case.transfer_eligible = False
    case.requires_human_oversight = False

    create_audit_event(
        case=case,
        event_type="ADMIN_COMBINED_RESET",
        actor=request.actor,
        message=request.reason,
        details={"old_state": old_state, "new_state": case.current_state.value},
    )
    save_case(case)

    subject = subject_registry.set_state(
        subject_id=request.subject_id,
        state=SubjectControlState.NORMAL,
        reason=request.reason,
        linked_case_id=request.case_id,
    )

    return {
        "message": "Combined admin reset completed.",
        "case_id": request.case_id,
        "subject_id": request.subject_id,
        "case_new_state": case.current_state.value,
        "subject": subject,
    }


@app.get("/quarantine/metrics")
def quarantine_metrics_json() -> Dict[str, Any]:
    return metrics_snapshot()


@app.get("/metrics", response_class=PlainTextResponse)
def quarantine_metrics_prometheus() -> str:
    return render_prometheus_metrics(metrics_snapshot())


@app.post("/quarantine")
def create_quarantine_case(request: QuarantineCreateRequest) -> Dict[str, Any]:
    submission = request.submission or {}
    normalized_payload = request.normalized_payload or {}
    risk_assessment = request.risk_assessment or {}
    decision_result_payload = request.decision_result or {}

    if not submission:
        raise HTTPException(status_code=400, detail="Missing submission payload.")

    try:
        decision_result = DecisionResult.model_validate(decision_result_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid decision_result payload: {exc}")

    policy = build_quarantine_policy_result(risk_assessment, decision_result)
    subject_id = (
        submission.get("payload", {}).get("data", {}).get("person_id")
        or normalized_payload.get("person_id")
    )

    case = QuarantineCase(
        submission=submission,
        normalized_payload=normalized_payload,
        risk_assessment=risk_assessment,
        decision_result=decision_result.model_dump(mode="json"),
        subject_id=subject_id,
        source_agent=request.source_agent,
        upstream_agent_reasoning=request.agent_reasoning,
        current_state=policy["initial_state"],
        isolation_mode=policy["isolation_mode"],
        severity=policy["severity"],
        decision_snapshot=policy["decision_snapshot"],
        release_eligible=policy["release_eligible"],
        transfer_eligible=policy["transfer_eligible"],
        requires_human_oversight=policy["requires_human_oversight"],
    )

    observation = create_observation(
        source=request.source_agent,
        kind="decision_snapshot",
        value={
            "action": decision_result.action.value,
            "risk_score": risk_assessment.get("total_score", 0.0),
            "severity": case.severity.value,
            "isolation_mode": case.isolation_mode.value,
            "handoff": decision_result.handoff.value,
            "agent_reasoning": request.agent_reasoning,
            "agent_details": request.agent_details,
        },
        confidence=request.agent_confidence or risk_assessment.get("confidence"),
    )
    case.observations.append(observation)

    create_audit_event(
        case=case,
        event_type="CASE_CREATED",
        actor="quarantine_service",
        message="Case created in containment.",
        details={
            "initial_state": case.current_state.value,
            "isolation_mode": case.isolation_mode.value,
            "severity": case.severity.value,
            "handoff": decision_result.handoff.value,
            "source_agent": request.source_agent,
        },
    )

    if case.subject_id:
        subject_registry.upsert(
            subject_id=case.subject_id,
            state=SubjectControlState.RESTRICTED,
            reason="subject_entered_containment",
            linked_case_id=case.case_id,
        )

    save_case(case)

    return {
        "message": "Submission quarantined successfully.",
        "case_id": case.case_id,
        "status": case.current_state.value,
        "severity": case.severity.value,
        "isolation_mode": case.isolation_mode.value,
        "risk_score": risk_assessment.get("total_score", 0.0),
    }


@app.get("/quarantine")
def list_quarantine_cases() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(QUARANTINE_DIR.glob("*.json"), reverse=True):
        try:
            case = QuarantineCase.model_validate(json.loads(path.read_text(encoding="utf-8")))
            cases.append(case_summary(case))
        except Exception:
            continue
    return {"cases": cases}


@app.get("/quarantine/{case_id}")
def get_quarantine_case(case_id: str) -> Dict[str, Any]:
    case = load_case(case_id)
    return case.model_dump(mode="json")


@app.post("/quarantine/{case_id}/hold")
def hold_case(case_id: str, request: CaseActionRequest) -> Dict[str, Any]:
    case = load_case(case_id)
    old_state = case.current_state.value

    try:
        apply_state_transition(case, QuarantineState.CONTAINED)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    case.release_eligible = False

    create_audit_event(
        case=case,
        event_type="CASE_HELD",
        actor=request.actor,
        message=request.message or "Case kept inside containment.",
        details={"old_state": old_state, **request.details},
    )

    save_case(case)
    return {
        "message": "Case held in containment.",
        "case_id": case.case_id,
        "old_state": old_state,
        "new_state": case.current_state.value,
    }


@app.post("/quarantine/{case_id}/human-oversight")
def human_oversight_case(case_id: str, request: CaseActionRequest) -> Dict[str, Any]:
    case = load_case(case_id)
    old_state = case.current_state.value

    try:
        apply_state_transition(case, QuarantineState.UNDER_REVIEW)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    case.requires_human_oversight = True

    create_audit_event(
        case=case,
        event_type="CASE_UNDER_REVIEW",
        actor=request.actor,
        message=request.message or "Case moved to human oversight.",
        details={"old_state": old_state, **request.details},
    )

    save_case(case)
    return {
        "message": "Case moved to human oversight.",
        "case_id": case.case_id,
        "old_state": old_state,
        "new_state": case.current_state.value,
    }


@app.post("/quarantine/{case_id}/release")
def release_case(case_id: str, request: CaseActionRequest) -> Dict[str, Any]:
    case = load_case(case_id)
    old_state = case.current_state.value

    try:
        apply_state_transition(case, QuarantineState.RELEASED)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    case.release_eligible = False
    case.transfer_eligible = False
    case.requires_human_oversight = False

    if case.subject_id:
        subject_registry.set_state(
            subject_id=case.subject_id,
            state=SubjectControlState.NORMAL,
            reason="manual_release_from_containment",
            linked_case_id=case.case_id,
        )

    create_audit_event(
        case=case,
        event_type="CASE_RELEASED",
        actor=request.actor,
        message=request.message or "Case released from containment.",
        details={"old_state": old_state, **request.details},
    )

    save_case(case)
    return {
        "message": "Case released.",
        "case_id": case.case_id,
        "old_state": old_state,
        "new_state": case.current_state.value,
    }


@app.post("/quarantine/{case_id}/transfer")
def transfer_case(case_id: str, request: CaseActionRequest) -> Dict[str, Any]:
    case = load_case(case_id)
    old_state = case.current_state.value

    downstream = forward_to_minefield(case)

    if not downstream.get("ok"):
        create_audit_event(
            case=case,
            event_type="TRANSFER_FAILED",
            actor=request.actor,
            message=request.message or "Transfer to minefield failed.",
            details={"old_state": old_state, "downstream_result": downstream, **request.details},
        )
        save_case(case)
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Downstream transfer failed.",
                "case_id": case.case_id,
                "downstream_result": downstream,
            },
        )

    try:
        apply_state_transition(case, QuarantineState.TRANSFERRED)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    case.transfer_target = "MINEFIELD"
    case.transfer_eligible = False
    case.release_eligible = False

    if case.subject_id:
        subject_registry.upsert(
            subject_id=case.subject_id,
            state=SubjectControlState.BLOCKED,
            reason="subject_escalated_to_minefield",
            linked_case_id=case.case_id,
        )

    create_audit_event(
        case=case,
        event_type="CASE_TRANSFERRED",
        actor=request.actor,
        message=request.message or "Case transferred to minefield.",
        details={"old_state": old_state, "downstream_result": downstream, **request.details},
    )

    save_case(case)
    return {
        "message": "Case transferred.",
        "case_id": case.case_id,
        "old_state": old_state,
        "new_state": case.current_state.value,
        "transfer_target": case.transfer_target,
        "downstream_result": downstream,
    }


@app.post("/quarantine/{case_id}/analyze")
def analyze_case(case_id: str) -> Dict[str, Any]:
    case = load_case(case_id)
    advisory = advisory_engine(case)

    observation = create_observation(
        source="containment_advisor",
        kind="containment_advisory",
        value={
            "recommended_handoff": advisory.recommended_handoff.value,
            "recommended_target": advisory.recommended_target,
            "reasoning": advisory.reasoning,
            "risk_narrative": advisory.risk_narrative,
            "should_require_human": advisory.should_require_human,
        },
        confidence=advisory.confidence,
    )
    case.observations.append(observation)

    create_audit_event(
        case=case,
        event_type="CASE_ANALYZED",
        actor="containment_advisor",
        message="Containment advisory generated.",
        details={
            "recommended_handoff": advisory.recommended_handoff.value,
            "recommended_target": advisory.recommended_target,
            "confidence": advisory.confidence,
            "should_require_human": advisory.should_require_human,
        },
    )

    save_case(case)
    return advisory.model_dump(mode="json")


@app.post("/quarantine/{case_id}/apply-advisory")
def apply_advisory(case_id: str, request: ApplyAdvisoryRequest) -> Dict[str, Any]:
    case = load_case(case_id)
    advisory = advisory_engine(case)

    if advisory.should_require_human and not request.force_human_override:
        create_audit_event(
            case=case,
            event_type="ADVISORY_BLOCKED",
            actor=request.actor,
            message="Advisory recommended human oversight; automatic execution blocked.",
            details={"recommended_handoff": advisory.recommended_handoff.value},
        )
        save_case(case)
        return {
            "message": "Automatic application blocked pending human oversight.",
            "case_id": case.case_id,
            "recommended_handoff": advisory.recommended_handoff.value,
        }

    if advisory.recommended_handoff == AdvisoryHandoff.HOLD:
        old_state = case.current_state.value
        apply_state_transition(case, QuarantineState.CONTAINED)
        create_audit_event(
            case=case,
            event_type="ADVISORY_APPLIED",
            actor=request.actor,
            message="Containment advisory applied: HOLD.",
            details={"old_state": old_state, "new_state": case.current_state.value},
        )

    elif advisory.recommended_handoff == AdvisoryHandoff.NEEDS_HUMAN_OVERSIGHT:
        old_state = case.current_state.value
        apply_state_transition(case, QuarantineState.UNDER_REVIEW)
        case.requires_human_oversight = True
        create_audit_event(
            case=case,
            event_type="ADVISORY_APPLIED",
            actor=request.actor,
            message="Containment advisory applied: NEEDS_HUMAN_OVERSIGHT.",
            details={"old_state": old_state, "new_state": case.current_state.value},
        )

    elif advisory.recommended_handoff == AdvisoryHandoff.TRANSFER_TO_MINEFIELD:
        old_state = case.current_state.value
        downstream = forward_to_minefield(case)

        if not downstream.get("ok"):
            create_audit_event(
                case=case,
                event_type="TRANSFER_FAILED",
                actor=request.actor,
                message="Containment advisory transfer to minefield failed.",
                details={"old_state": old_state, "downstream_result": downstream},
            )
            save_case(case)
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Downstream transfer failed during advisory application.",
                    "case_id": case.case_id,
                    "downstream_result": downstream,
                },
            )

        apply_state_transition(case, QuarantineState.TRANSFERRED)
        case.transfer_target = "MINEFIELD"
        if case.subject_id:
            subject_registry.upsert(
                subject_id=case.subject_id,
                state=SubjectControlState.BLOCKED,
                reason="subject_escalated_to_minefield",
                linked_case_id=case.case_id,
            )
        create_audit_event(
            case=case,
            event_type="ADVISORY_APPLIED",
            actor=request.actor,
            message="Containment advisory applied: TRANSFER_TO_MINEFIELD.",
            details={
                "old_state": old_state,
                "new_state": case.current_state.value,
                "downstream_result": downstream,
            },
        )

    elif advisory.recommended_handoff == AdvisoryHandoff.RELEASE:
        old_state = case.current_state.value
        apply_state_transition(case, QuarantineState.RELEASED)
        if case.subject_id:
            subject_registry.set_state(
                subject_id=case.subject_id,
                state=SubjectControlState.NORMAL,
                reason="release_after_containment_review",
                linked_case_id=case.case_id,
            )
        create_audit_event(
            case=case,
            event_type="ADVISORY_APPLIED",
            actor=request.actor,
            message="Containment advisory applied: RELEASE.",
            details={"old_state": old_state, "new_state": case.current_state.value},
        )

    save_case(case)
    return {
        "message": "Containment advisory applied.",
        "case_id": case.case_id,
        "new_state": case.current_state.value,
        "transfer_target": case.transfer_target,
        "recommended_handoff": advisory.recommended_handoff.value,
    }
