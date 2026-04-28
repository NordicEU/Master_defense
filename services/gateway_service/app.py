from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException

from shared.models.decision import DefenseAction

app = FastAPI(title="Gateway Service", version="8.0.0")

DECISION_URL = os.getenv("DECISION_URL", "http://127.0.0.1:8002/decide")
CONTAIN_URL = os.getenv("CONTAIN_URL", "http://127.0.0.1:8003/quarantine")
ALLOW_URL = os.getenv("ALLOW_URL", "http://127.0.0.1:8004/process")
HONEYPOT_URL = os.getenv("HONEYPOT_URL", "http://127.0.0.1:8005/review")
MINEFIELD_URL = os.getenv("MINEFIELD_URL", "http://127.0.0.1:8006/defer")
DECEIVE_URL = os.getenv("DECEIVE_URL", "http://127.0.0.1:8007/deception")

RULE_ENGINE_URL = os.getenv("RULE_ENGINE_URL", "http://127.0.0.1:8011/analyze")
ANOMALY_SCORER_URL = os.getenv("ANOMALY_SCORER_URL", "http://127.0.0.1:8012/score")
CONTEXT_VALIDATOR_URL = os.getenv("CONTEXT_VALIDATOR_URL", "http://127.0.0.1:8013/validate")
SEMANTIC_ASSIST_URL = os.getenv("SEMANTIC_ASSIST_URL", "http://127.0.0.1:8014/analyze")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "gateway_service"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            try:
                return {
                    "status_code": response.status_code,
                    "json": response.json(),
                }
            except Exception:
                return {
                    "status_code": response.status_code,
                    "text": response.text,
                }
    except httpx.HTTPStatusError as exc:
        detail_text = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(
            status_code=502,
            detail=f"Downstream HTTP error from {url}: {detail_text}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gateway HTTP error from {url}: {exc}",
        )


def _extract_findings(*analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for result in analysis_results:
        result_json = result.get("json", {})
        raw_findings = result_json.get("findings", [])
        if isinstance(raw_findings, list):
            for finding in raw_findings:
                if isinstance(finding, dict):
                    findings.append(finding)
    return findings


def _context_finding_strings(findings: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for finding in findings:
        finding_type = _safe_str(finding.get("finding_type"))
        message = _safe_str(finding.get("message"))
        rule_id = _safe_str(finding.get("rule_id"))
        if finding_type:
            out.append(finding_type)
        if message:
            out.append(message)
        if rule_id:
            out.append(rule_id)
    return out


def _max_score(items: List[Dict[str, Any]]) -> float:
    scores: List[float] = []
    for item in items:
        try:
            scores.append(float(item.get("score", 0.0) or 0.0))
        except Exception:
            continue
    return max(scores) if scores else 0.0


def _summarize_finding_types(findings: List[Dict[str, Any]]) -> List[str]:
    values: List[str] = []
    for finding in findings:
        finding_type = _safe_str(finding.get("finding_type")).lower()
        if finding_type and finding_type not in values:
            values.append(finding_type)
    return values


def _fuse_risk_assessment(
    normalized_payload: Dict[str, Any],
    rule_result: Dict[str, Any],
    anomaly_result: Dict[str, Any],
    context_result: Dict[str, Any],
    semantic_result: Dict[str, Any],
) -> Dict[str, Any]:
    rule_json = rule_result.get("json", {})
    anomaly_json = anomaly_result.get("json", {})
    context_json = context_result.get("json", {})
    semantic_json = semantic_result.get("json", {})

    rule_score = float(rule_json.get("rule_score", 0.05) or 0.05)
    statistical_score = float(anomaly_json.get("statistical_score", 0.08) or 0.08)
    context_score = float(context_json.get("context_score", 0.10) or 0.10)
    semantic_score = float(semantic_json.get("score", 0.0) or 0.0)

    all_findings = _extract_findings(rule_result, anomaly_result, context_result)
    finding_types = _summarize_finding_types(all_findings)

    semantic_reason = _safe_str(semantic_json.get("reason"))
    semantic_explanation = _safe_str(semantic_json.get("explanation"))
    semantic_flag = bool(semantic_json.get("flag", False))
    semantic_assessment = _safe_str(semantic_json.get("assessment"))
    semantic_confidence = _safe_str(semantic_json.get("confidence"))

    highest_finding_score = _max_score(all_findings)

    total_score = (
        0.35 * rule_score
        + 0.25 * statistical_score
        + 0.25 * context_score
        + 0.15 * semantic_score
    )

    total_score = max(total_score, highest_finding_score)
    total_score = round(min(max(total_score, 0.0), 1.0), 2)

    if semantic_flag and semantic_reason and semantic_reason.lower() not in finding_types:
        finding_types.append(semantic_reason.lower())

    if semantic_flag and semantic_explanation:
        semantic_reasoning = f"Detected indicators: {', '.join(finding_types)} | semantic: {semantic_explanation}"
    elif finding_types:
        semantic_reasoning = f"Detected indicators: {', '.join(finding_types)}"
    else:
        semantic_reasoning = "No strong structural anomaly detected."

    confidence = 0.70
    if total_score >= 0.90:
        confidence = 0.94
    elif total_score >= 0.75:
        confidence = 0.88
    elif total_score >= 0.55:
        confidence = 0.80
    elif total_score >= 0.35:
        confidence = 0.72

    recommended_action = "CONTAIN" if total_score >= 0.55 else "ALLOW"

    return {
        "assessment_id": str(uuid4()),
        "rule_score": round(rule_score, 2),
        "statistical_score": round(statistical_score, 2),
        "context_score": round(context_score, 2),
        "semantic_score": round(semantic_score, 2),
        "total_score": total_score,
        "confidence": round(confidence, 2),
        "findings": all_findings,
        "finding_types": finding_types,
        "semantic_reasoning": semantic_reasoning,
        "semantic_reason": semantic_reason,
        "semantic_assessment": semantic_assessment,
        "semantic_confidence": semantic_confidence,
        "recommended_action": recommended_action,
        "assessed_at": utc_now_iso(),
        "normalized_subject_id": _safe_str(normalized_payload.get("person_id")),
    }


def _build_fused_analysis(normalized_payload: Dict[str, Any]) -> Dict[str, Any]:
    rule_result = _post_json(RULE_ENGINE_URL, {"normalized_payload": normalized_payload})
    anomaly_result = _post_json(ANOMALY_SCORER_URL, {"normalized_payload": normalized_payload})
    context_result = _post_json(CONTEXT_VALIDATOR_URL, {"normalized_payload": normalized_payload})

    context_findings_raw = context_result.get("json", {}).get("findings", [])
    context_findings = _context_finding_strings(
        context_findings_raw if isinstance(context_findings_raw, list) else []
    )

    semantic_result = _post_json(
        SEMANTIC_ASSIST_URL,
        {
            "normalized_payload": normalized_payload,
            "context_findings": context_findings,
        },
    )

    fused_risk = _fuse_risk_assessment(
        normalized_payload=normalized_payload,
        rule_result=rule_result,
        anomaly_result=anomaly_result,
        context_result=context_result,
        semantic_result=semantic_result,
    )

    return {
        "risk_assessment": fused_risk,
        "analysis_trace": {
            "rule_engine": rule_result.get("json", {}),
            "anomaly_scorer": anomaly_result.get("json", {}),
            "context_validator": context_result.get("json", {}),
            "semantic_assist": semantic_result.get("json", {}),
        },
    }


def _build_common_payload(
    submission: Dict[str, Any],
    normalized_payload: Dict[str, Any],
    risk_assessment: Dict[str, Any],
    decision_result: Dict[str, Any],
    analysis_trace: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "submission": submission,
        "normalized_payload": normalized_payload,
        "risk_assessment": risk_assessment,
        "decision_result": decision_result,
        "analysis_trace": analysis_trace,
        "source_agent": "gateway",
        "agent_reasoning": (
            risk_assessment.get("semantic_reasoning")
            or "Initial intrusion detection routed the submission based on fused analysis."
        ),
        "agent_details": {
            "analysis_trace": analysis_trace,
            "initial_detection_recommended_action": risk_assessment.get("recommended_action"),
            "decision_service_action": decision_result.get("action"),
            "decision_service_handoff": decision_result.get("handoff"),
            "finding_types": risk_assessment.get("finding_types", []),
        },
    }


@app.post("/route")
def route_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    submission = payload.get("submission")
    normalized_payload = payload.get("normalized_payload")

    if not isinstance(submission, dict) or not isinstance(normalized_payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid submission or normalized_payload.",
        )

    fused = _build_fused_analysis(normalized_payload)
    risk_assessment = fused["risk_assessment"]
    analysis_trace = fused["analysis_trace"]

    decision_payload = {
        "submission": submission,
        "normalized_payload": normalized_payload,
        "risk_assessment": risk_assessment,
    }

    decision_response = _post_json(DECISION_URL, decision_payload)
    decision_result = decision_response.get("json")

    if not isinstance(decision_result, dict):
        raise HTTPException(
            status_code=502,
            detail="Decision service returned an invalid response.",
        )

    action = _safe_str(decision_result.get("action")).upper()
    handoff = _safe_str(decision_result.get("handoff")).upper()

    common_payload = _build_common_payload(
        submission=submission,
        normalized_payload=normalized_payload,
        risk_assessment=risk_assessment,
        decision_result=decision_result,
        analysis_trace=analysis_trace,
    )

    if action == DefenseAction.CONTAIN.value:
        downstream = _post_json(CONTAIN_URL, common_payload)
        return {
            "submission_id": submission.get("submission_id", "unknown"),
            "flow_result": "CONTAIN",
            "action": action,
            "handoff": handoff,
            "risk_assessment": risk_assessment,
            "downstream_status": downstream["status_code"],
            "downstream_response": downstream.get("json") or downstream.get("text"),
        }

    if action == DefenseAction.ALLOW.value:
        downstream = _post_json(ALLOW_URL, common_payload)
        return {
            "submission_id": submission.get("submission_id", "unknown"),
            "flow_result": "ALLOW",
            "action": action,
            "handoff": handoff,
            "risk_assessment": risk_assessment,
            "downstream_status": downstream["status_code"],
            "downstream_response": downstream.get("json") or downstream.get("text"),
        }

    if action == DefenseAction.HONEYPOT.value:
        downstream = _post_json(HONEYPOT_URL, common_payload)
        return {
            "submission_id": submission.get("submission_id", "unknown"),
            "flow_result": "HONEYPOT",
            "action": action,
            "handoff": handoff,
            "risk_assessment": risk_assessment,
            "downstream_status": downstream["status_code"],
            "downstream_response": downstream.get("json") or downstream.get("text"),
        }

    if action == DefenseAction.DECEIVE.value:
        downstream = _post_json(DECEIVE_URL, common_payload)
        return {
            "submission_id": submission.get("submission_id", "unknown"),
            "flow_result": "DECEIVE",
            "action": action,
            "handoff": handoff,
            "risk_assessment": risk_assessment,
            "downstream_status": downstream["status_code"],
            "downstream_response": downstream.get("json") or downstream.get("text"),
        }

    if action == DefenseAction.MINEFIELD.value:
        downstream = _post_json(MINEFIELD_URL, common_payload)
        return {
            "submission_id": submission.get("submission_id", "unknown"),
            "flow_result": "MINEFIELD",
            "action": action,
            "handoff": handoff,
            "risk_assessment": risk_assessment,
            "downstream_status": downstream["status_code"],
            "downstream_response": downstream.get("json") or downstream.get("text"),
        }

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported defense action from decision service: {action}",
    )
