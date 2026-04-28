from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel, Field
from ollama import chat

app = FastAPI(title="Semantic Assist", version="4.0.0")

MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


class SemanticRequest(BaseModel):
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    context_findings: List[str] = Field(default_factory=list)


def build_prompt(payload: Dict[str, Any], context_findings: List[str]) -> str:
    return f"""
You are a conservative semantic fraud detector inside an embedded application defense system.

Your role:
- You are NOT the primary decision-maker.
- You are a semantic support layer.
- You must be cautious and avoid overclaiming malicious intent.
- You must NOT invent tax rules, legal rules, or unsupported accusations.
- You must rely on the provided payload and context findings only.

Decision rules:
- If context findings are empty, prefer benign unless the payload is obviously self-contradictory.
- If context findings contain clear identity mismatch, forged context, deceptive wording, or implausible semantics, you may classify as suspicious.
- Do not escalate solely because a number is large. Structural and contextual meaning matter more.
- Return only valid JSON and nothing else.

Return exactly this JSON format:
{{
  "assessment": "benign" or "suspicious",
  "confidence": "low" or "medium" or "high",
  "reason": "short_machine_readable_reason",
  "explanation": "short human-readable explanation"
}}

Payload:
{json.dumps(payload, ensure_ascii=False)}

Context findings:
{json.dumps(context_findings, ensure_ascii=False)}
""".strip()


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw_text[start:end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Could not extract valid JSON object from LLM response")


def normalize_llm_result(result: Dict[str, Any], context_findings: List[str]) -> Dict[str, Any]:
    assessment = str(result.get("assessment", "")).strip().lower()
    confidence = str(result.get("confidence", "")).strip().lower()
    reason = str(result.get("reason") or "").strip()
    explanation = str(result.get("explanation") or "").strip()

    normalized_context = [str(x).strip().lower() for x in context_findings if str(x).strip()]

    strong_context_terms = [
        "identity_mismatch",
        "forged_context",
        "context_mismatch",
        "employment_inconsistency",
        "deceptive",
        "semantic_manipulation",
        "unknown_employer",
    ]
    has_strong_context = any(
        term in item for item in normalized_context for term in strong_context_terms
    )

    if not normalized_context:
        assessment = "benign"
        confidence = "low"
        if not reason:
            reason = "no_contextual_basis_for_semantic_escalation"
        if not explanation:
            explanation = "No contextual findings were present, so semantic escalation was suppressed."

    if assessment not in {"benign", "suspicious"}:
        assessment = "benign"

    if confidence not in {"low", "medium", "high"}:
        confidence = "low"

    if assessment == "suspicious" and not has_strong_context:
        assessment = "benign"
        confidence = "low"
        if not reason:
            reason = "semantic_signal_without_contextual_support"
        if not explanation:
            explanation = "Semantic suspicion was downgraded because contextual support was insufficient."

    flag = False
    score = 0.0

    if assessment == "suspicious":
        flag = True
        if confidence == "high":
            score = 0.22
        elif confidence == "medium":
            score = 0.15
        else:
            score = 0.08

    if not reason:
        reason = "semantic_assessment_unavailable"
    if not explanation:
        explanation = "No explanation returned."

    return {
        "flag": flag,
        "score": round(min(max(score, 0.0), 0.30), 2),
        "reason": reason,
        "explanation": explanation,
        "assessment": assessment,
        "confidence": confidence,
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "semantic_assist", "model": MODEL_NAME}


@app.post("/analyze")
def analyze_semantics(request: SemanticRequest) -> Dict[str, Any]:
    prompt = build_prompt(request.normalized_payload, request.context_findings)

    try:
        response = chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_model_output = response["message"]["content"]
        parsed = _extract_json_object(raw_model_output)
        return normalize_llm_result(parsed, request.context_findings)
    except Exception as exc:
        return {
            "flag": False,
            "score": 0.0,
            "reason": "llm_unavailable",
            "explanation": f"LLM semantic analysis unavailable: {exc}",
            "assessment": "benign",
            "confidence": "low",
        }
