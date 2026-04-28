from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Business App", version="1.1.0")

BASE_DIR = Path(__file__).resolve().parents[2]
BUSINESS_LOG_DIR = BASE_DIR / "runtime" / "metrics"
BUSINESS_LOG_DIR.mkdir(parents=True, exist_ok=True)
BUSINESS_ACCEPTED_PATH = BUSINESS_LOG_DIR / "accepted_submissions.jsonl"


class BusinessSubmission(BaseModel):
    submission: Dict[str, Any] = Field(default_factory=dict)
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)
    decision_result: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "business_app"}


@app.post("/process")
def process_submission(request: BusinessSubmission) -> Dict[str, Any]:
    record = {
        "submission": request.submission,
        "normalized_payload": request.normalized_payload,
        "decision_result": request.decision_result,
    }

    with BUSINESS_ACCEPTED_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    submission_id = request.submission.get("submission_id", "unknown")

    return {
        "message": "Submission accepted by business application.",
        "submission_id": submission_id,
        "stored_at": str(BUSINESS_ACCEPTED_PATH),
    }


@app.get("/accepted")
def list_accepted() -> Dict[str, List[Dict[str, Any]]]:
    items: List[Dict[str, Any]] = []

    if BUSINESS_ACCEPTED_PATH.exists():
        with BUSINESS_ACCEPTED_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))

    return {"accepted_submissions": items}


@app.get("/accepted/{submission_id}")
def get_accepted_submission(submission_id: str) -> Dict[str, Any]:
    if BUSINESS_ACCEPTED_PATH.exists():
        with BUSINESS_ACCEPTED_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if item.get("submission", {}).get("submission_id") == submission_id:
                    return item

    raise HTTPException(status_code=404, detail="Accepted submission not found.")
