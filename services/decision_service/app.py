from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.models.findings import AnalysisFinding
from shared.models.risk import RiskAssessment
from shared.policies.decision_policy import build_decision_result

app = FastAPI(title="Decision Service", version="5.0.0")


class DecisionRequest(BaseModel):
    submission: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return default


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _parse_findings(raw_findings: Any) -> List[AnalysisFinding]:
    findings: List[AnalysisFinding] = []

    if not isinstance(raw_findings, list):
        return findings

    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        try:
            findings.append(AnalysisFinding.model_validate(item))
        except Exception:
            continue

    return findings


def _build_risk_model(risk_assessment_payload: Dict[str, Any]) -> RiskAssessment:
    findings = _parse_findings(risk_assessment_payload.get("findings", []))

    return RiskAssessment(
        assessment_id=_safe_str(risk_assessment_payload.get("assessment_id")) or "unknown-assessment",
        rule_score=_safe_float(risk_assessment_payload.get("rule_score"), 0.0),
        statistical_score=_safe_float(risk_assessment_payload.get("statistical_score"), 0.0),
        context_score=_safe_float(risk_assessment_payload.get("context_score"), 0.0),
        semantic_score=_safe_float(risk_assessment_payload.get("semantic_score"), 0.0),
        total_score=_safe_float(risk_assessment_payload.get("total_score"), 0.0),
        confidence=_safe_float(risk_assessment_payload.get("confidence"), 0.0),
        findings=findings,
        semantic_reasoning=_safe_str(risk_assessment_payload.get("semantic_reasoning")),
        semantic_assessment=_safe_str(risk_assessment_payload.get("semantic_assessment")),
        recommended_action=_safe_str(risk_assessment_payload.get("recommended_action")),
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "decision_service"}


@app.post("/decide")
def decide(request: DecisionRequest) -> Dict[str, Any]:
    if not isinstance(request.submission, dict) or not request.submission:
        raise HTTPException(status_code=400, detail="Missing submission payload.")

    if not isinstance(request.normalized_payload, dict) or not request.normalized_payload:
        raise HTTPException(status_code=400, detail="Missing normalized_payload.")

    if not isinstance(request.risk_assessment, dict) or not request.risk_assessment:
        raise HTTPException(status_code=400, detail="Missing risk_assessment.")

    try:
        risk = _build_risk_model(request.risk_assessment)
        decision = build_decision_result(risk)
        return decision.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Decision evaluation failed: {exc}")
