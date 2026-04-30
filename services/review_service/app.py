from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Review Service", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parents[2]
REVIEW_DIR = BASE_DIR / "runtime" / "review_cases"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_path(review_id: str) -> Path:
    return REVIEW_DIR / f"{review_id}.json"


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_case(review_id: str) -> Dict[str, Any]:
    path = case_path(review_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Review case not found.")
    return json.loads(path.read_text(encoding="utf-8"))


class ReviewRequest(BaseModel):
    submission: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    decision_result: Dict[str, Any] = Field(default_factory=dict)
    source_agent: str = "gateway"
    agent_reasoning: str | None = None
    agent_details: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "review_service"}


@app.post("/review")
def review_case(request: ReviewRequest) -> Dict[str, Any]:
    if not request.submission:
        raise HTTPException(status_code=400, detail="Missing submission payload.")

    review_id = str(uuid4())
    received_at = utc_now_iso()
    record = {
        "review_id": review_id,
        "status": "queued_review",
        "received_at": received_at,
        "submission": request.submission,
        "normalized_payload": request.normalized_payload,
        "risk_assessment": request.risk_assessment,
        "decision_result": request.decision_result,
        "source_agent": request.source_agent,
        "agent_reasoning": request.agent_reasoning,
        "agent_details": request.agent_details,
        "review_notes": {
            "routing_reason": "Submission routed to honeypot/review handling.",
        },
    }
    write_json(case_path(review_id), record)

    return {
        "message": "Submission accepted into review handling.",
        "status": record["status"],
        "review_id": review_id,
        "submission_id": request.submission.get("submission_id", "unknown"),
        "received_at": received_at,
    }


@app.get("/review")
def list_review_cases() -> Dict[str, List[Dict[str, Any]]]:
    cases: List[Dict[str, Any]] = []
    for path in sorted(REVIEW_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            cases.append(data)
    return {"cases": cases}


@app.get("/review/{review_id}")
def get_review_case(review_id: str) -> Dict[str, Any]:
    return load_case(review_id)
