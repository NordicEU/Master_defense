from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
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


def _load_accepted_items() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if BUSINESS_ACCEPTED_PATH.exists():
        with BUSINESS_ACCEPTED_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))

    return items


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    items = _load_accepted_items()
    total_accepted = len(items)
    recent_items = list(reversed(items[-5:]))

    recent_rows = []
    for item in recent_items:
        submission = item.get("submission", {})
        decision = item.get("decision_result", {})
        submission_id = str(submission.get("submission_id", "unknown"))
        person_id = str(submission.get("person_id", "-"))
        employer_id = str(submission.get("employer_id", "-"))
        action = str(decision.get("action", "ALLOW"))
        recent_rows.append(
            f"""
            <tr>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;"><a href="/accepted/{submission_id}">{submission_id}</a></td>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;">{person_id}</td>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;">{employer_id}</td>
                <td style="padding:10px;border-bottom:1px solid #e5e7eb;">{action}</td>
            </tr>
            """
        )

    if not recent_rows:
        recent_rows.append(
            """
            <tr>
                <td colspan="4" style="padding:10px;border-bottom:1px solid #e5e7eb;">No accepted submissions yet.</td>
            </tr>
            """
        )

    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Business App</title>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 960px; margin: 40px auto; padding: 20px; line-height: 1.5;">
        <h1>Business App</h1>
        <p>This service receives accepted submissions from the gateway and stores them for later review.</p>
        <div style="display:grid;grid-template-columns:220px 1fr;gap:16px;align-items:start;margin-top:24px;">
            <div style="border:1px solid #d1d5db;border-radius:12px;padding:18px;">
                <div style="font-size:14px;color:#4b5563;">Accepted requests</div>
                <div style="font-size:40px;font-weight:700;margin-top:8px;">{total_accepted}</div>
            </div>
            <div style="border:1px solid #d1d5db;border-radius:12px;padding:18px;">
                <div style="font-size:14px;color:#4b5563;margin-bottom:10px;">Quick links</div>
                <div style="display:flex;gap:16px;flex-wrap:wrap;">
                    <a href="/health">Health</a>
                    <a href="/accepted">Raw accepted submissions</a>
                </div>
                <p style="margin-top:14px;"><strong>POST endpoint:</strong> <code>/process</code></p>
            </div>
        </div>
        <div style="margin-top:28px;border:1px solid #d1d5db;border-radius:12px;padding:18px;">
            <h2 style="margin-top:0;">Recent Accepted Submissions</h2>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr>
                        <th style="text-align:left;padding:10px;border-bottom:1px solid #d1d5db;">Submission ID</th>
                        <th style="text-align:left;padding:10px;border-bottom:1px solid #d1d5db;">Person ID</th>
                        <th style="text-align:left;padding:10px;border-bottom:1px solid #d1d5db;">Employer ID</th>
                        <th style="text-align:left;padding:10px;border-bottom:1px solid #d1d5db;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(recent_rows)}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(body)


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
    return {"accepted_submissions": _load_accepted_items()}


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
