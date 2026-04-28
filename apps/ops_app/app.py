from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / "runtime"

CONTAIN_DIR = RUNTIME_DIR / "quarantine_cases"
DECEIVE_DIR = RUNTIME_DIR / "deception_cases"
HONEYPOT_DIR = RUNTIME_DIR / "review_cases"
MINEFIELD_DIR = RUNTIME_DIR / "defer_cases"
ALLOW_DIR = RUNTIME_DIR / "business_accepted"
SUBJECT_CONTROL_DIR = CONTAIN_DIR / "subject_control"

QUARANTINE_ADMIN_BASE = os.getenv("QUARANTINE_ADMIN_BASE", "http://quarantine-service:8003")

for path in [CONTAIN_DIR, DECEIVE_DIR, HONEYPOT_DIR, MINEFIELD_DIR, ALLOW_DIR, SUBJECT_CONTROL_DIR]:
    path.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Defense Ops Dashboard", version="4.0.0")


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _load_json_files(folder: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not folder.exists():
        return items

    for path in sorted(folder.glob("*.json"), reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                items.append(json.load(f))
        except Exception:
            continue
    return items


def _page(title: str, body: str) -> HTMLResponse:
    html_doc = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{html.escape(title)}</title>
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 1280px; margin: 40px auto; padding: 20px;">
        {_nav()}
        {body}
    </body>
    </html>
    """
    return HTMLResponse(content=html_doc)


def _nav() -> str:
    return """
    <div style="display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap;">
        <a href="/ops">Overview</a>
        <a href="/ops/contain">Contain</a>
        <a href="/ops/deceive">Deceive</a>
        <a href="/ops/honeypot">Honeypot</a>
        <a href="/ops/minefield">Minefield</a>
        <a href="/ops/allow">Allow</a>
        <a href="/ops/subjects">Subjects</a>
    </div>
    """


def _badge(text: str, bg: str = "#e5e7eb", fg: str = "#111827") -> str:
    return (
        f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;'
        f'background:{bg};color:{fg};font-size:12px;">{html.escape(str(text))}</span>'
    )


def _state_badge(state: str) -> str:
    state = _safe_str(state).upper()
    if state == "NORMAL":
        return _badge(state, "#dcfce7", "#166534")
    if state == "RESTRICTED":
        return _badge(state, "#fef3c7", "#92400e")
    if state == "BLOCKED":
        return _badge(state, "#fee2e2", "#991b1b")
    if state == "CONTAINED":
        return _badge(state, "#dbeafe", "#1e3a8a")
    if state == "UNDER_REVIEW":
        return _badge(state, "#e0e7ff", "#3730a3")
    if state == "TRANSFERRED":
        return _badge(state, "#fee2e2", "#991b1b")
    if state == "RELEASED":
        return _badge(state, "#dcfce7", "#166534")
    return _badge(state or "UNKNOWN")


def _metric_card(title: str, value: Any) -> str:
    return f"""
    <div style="border:1px solid #ddd;padding:16px;border-radius:12px;">
        <div style="font-size:14px;color:#4b5563;">{html.escape(str(title))}</div>
        <div style="font-size:28px;font-weight:700;margin-top:8px;">{html.escape(str(value))}</div>
    </div>
    """


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "ops_app"}


@app.get("/ops", response_class=HTMLResponse)
def ops_overview() -> HTMLResponse:
    contain_cases = [item for item in _load_json_files(CONTAIN_DIR) if isinstance(item, dict) and "case_id" in item]
    deceive_cases = _load_json_files(DECEIVE_DIR)
    honeypot_cases = _load_json_files(HONEYPOT_DIR)
    minefield_cases = _load_json_files(MINEFIELD_DIR)
    allow_cases = _load_json_files(ALLOW_DIR)
    subject_records = _load_json_files(SUBJECT_CONTROL_DIR)

    restricted_count = sum(1 for s in subject_records if _safe_str(s.get("state")).upper() == "RESTRICTED")
    blocked_count = sum(1 for s in subject_records if _safe_str(s.get("state")).upper() == "BLOCKED")
    released_count = sum(1 for c in contain_cases if _safe_str(c.get("current_state")).upper() == "RELEASED")
    transferred_count = sum(1 for c in contain_cases if _safe_str(c.get("current_state")).upper() == "TRANSFERRED")

    body = f"""
    <h1>Defense Operations Dashboard</h1>
    <div style="display:grid;grid-template-columns:repeat(8,1fr);gap:14px;margin-top:24px;">
        {_metric_card("Contain cases", len(contain_cases))}
        {_metric_card("Deceive cases", len(deceive_cases))}
        {_metric_card("Honeypot cases", len(honeypot_cases))}
        {_metric_card("Minefield cases", len(minefield_cases))}
        {_metric_card("Allowed submissions", len(allow_cases))}
        {_metric_card("Restricted subjects", restricted_count)}
        {_metric_card("Blocked subjects", blocked_count)}
        {_metric_card("Released cases", released_count)}
    </div>
    <div style="margin-top:18px;">
        <p><strong>Transferred cases:</strong> {transferred_count}</p>
    </div>
    """
    return _page("Defense Ops Dashboard", body)


@app.get("/ops/subjects", response_class=HTMLResponse)
def subject_records() -> HTMLResponse:
    records = _load_json_files(SUBJECT_CONTROL_DIR)

    rows = []
    for record in records:
        subject_id = _safe_str(record.get("subject_id", "unknown"))
        state = _safe_str(record.get("state", "UNKNOWN"))
        reason = _safe_str(record.get("reason", ""))
        linked_case_ids = record.get("linked_case_ids", [])
        linked_case_ids = linked_case_ids if isinstance(linked_case_ids, list) else []
        latest_case_id = _safe_str(linked_case_ids[-1]) if linked_case_ids else ""

        action_html = "-"
        if state.upper() in {"RESTRICTED", "BLOCKED"} and latest_case_id:
            action_html = f"""
            <form method="post" action="/ops/subjects/reset" style="margin:0;">
                <input type="hidden" name="subject_id" value="{html.escape(subject_id)}">
                <input type="hidden" name="case_id" value="{html.escape(latest_case_id)}">
                <input type="hidden" name="actor" value="sensor_operator">
                <input type="hidden" name="reason" value="one click reset from subject list">
                <button type="submit" style="padding:6px 10px;">Release / Reset</button>
            </form>
            """

        rows.append(
            f"""
            <tr>
                <td><a href="/ops/subjects/{html.escape(subject_id)}">{html.escape(subject_id)}</a></td>
                <td>{_state_badge(state)}</td>
                <td>{html.escape(reason or "-")}</td>
                <td>{len(linked_case_ids)}</td>
                <td>{html.escape(_safe_str(record.get("updated_at", "")) or "-")}</td>
                <td>{action_html}</td>
            </tr>
            """
        )

    body = f"""
    <h1>Subject Control Records</h1>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th>Subject ID</th>
            <th>State</th>
            <th>Reason</th>
            <th>Linked Cases</th>
            <th>Updated At</th>
            <th>Action</th>
        </tr>
        {''.join(rows) or '<tr><td colspan="6">No subject records yet.</td></tr>'}
    </table>
    """
    return _page("Subject Control Records", body)


@app.get("/ops/subjects/{subject_id}", response_class=HTMLResponse)
def subject_record_detail(subject_id: str) -> HTMLResponse:
    path = SUBJECT_CONTROL_DIR / f"{subject_id}.json"
    if not path.exists():
        return _page("Subject Record Not Found", f"<h1>Subject record not found: {html.escape(subject_id)}</h1>")

    data = json.loads(path.read_text(encoding="utf-8"))
    state = _safe_str(data.get("state", "UNKNOWN"))
    linked_case_ids = data.get("linked_case_ids", [])
    linked_case_ids = linked_case_ids if isinstance(linked_case_ids, list) else []
    latest_case_id = _safe_str(linked_case_ids[-1]) if linked_case_ids else ""

    action_html = ""
    if state.upper() in {"RESTRICTED", "BLOCKED"} and latest_case_id:
        action_html = f"""
        <form method="post" action="/ops/subjects/reset" style="border:1px solid #ddd;padding:16px;border-radius:12px;margin-top:24px;max-width:760px;">
            <input type="hidden" name="subject_id" value="{html.escape(subject_id)}">
            <input type="hidden" name="case_id" value="{html.escape(latest_case_id)}">
            <input type="hidden" name="actor" value="sensor_operator">
            <input type="hidden" name="reason" value="reset from subject detail">
            <button type="submit" style="padding:10px 14px;">Release / Reset</button>
        </form>
        """

    body = f"""
    <h1>Subject Control Detail</h1>
    <div style="border:1px solid #ddd;padding:16px;border-radius:12px;">
        <p><strong>Subject ID:</strong> {html.escape(subject_id)}</p>
        <p><strong>State:</strong> {_state_badge(state)}</p>
        <p><strong>Reason:</strong> {html.escape(_safe_str(data.get("reason", "")) or "-")}</p>
        <p><strong>Updated At:</strong> {html.escape(_safe_str(data.get("updated_at", "")) or "-")}</p>
        <p><strong>Latest linked case:</strong> {html.escape(latest_case_id or "-")}</p>
    </div>
    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:12px;">
        <h3>Full Subject JSON</h3>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">{html.escape(json.dumps(data, indent=2))}</pre>
    </div>
    {action_html}
    """
    return _page(f"Subject {subject_id}", body)


@app.post("/ops/subjects/reset")
def ops_subject_reset(
    subject_id: str = Form(...),
    case_id: str = Form(...),
    actor: str = Form("sensor_operator"),
    reason: str = Form("one click reset"),
) -> RedirectResponse:
    payload = {
        "actor": actor,
        "reason": reason,
        "subject_id": subject_id,
        "case_id": case_id,
    }
    _post_json(f"{QUARANTINE_ADMIN_BASE}/admin/reset", payload)
    return RedirectResponse(url="/ops/subjects", status_code=303)


@app.get("/ops/contain", response_class=HTMLResponse)
def contain_cases() -> HTMLResponse:
    cases = [item for item in _load_json_files(CONTAIN_DIR) if isinstance(item, dict) and "case_id" in item]

    rows = []
    for case in cases:
        case_id = _safe_str(case.get("case_id", "unknown"))
        submission = case.get("submission", {})
        submission_id = _safe_str(submission.get("submission_id", "unknown"))
        current_state = _safe_str(case.get("current_state", "UNKNOWN"))
        severity = _safe_str(case.get("severity", "UNKNOWN"))
        isolation_mode = _safe_str(case.get("isolation_mode", "UNKNOWN"))
        risk = case.get("risk_assessment", {}).get("total_score", "n/a")
        subject_id = _safe_str(case.get("subject_id", ""))

        rows.append(
            f"""
            <tr>
                <td><a href="/ops/contain/{html.escape(case_id)}">{html.escape(case_id)}</a></td>
                <td>{html.escape(submission_id)}</td>
                <td>{html.escape(subject_id or "-")}</td>
                <td>{_state_badge(current_state)}</td>
                <td>{html.escape(severity)}</td>
                <td>{html.escape(isolation_mode)}</td>
                <td>{html.escape(str(risk))}</td>
            </tr>
            """
        )

    body = f"""
    <h1>Contain Cases</h1>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th>Case ID</th>
            <th>Submission ID</th>
            <th>Subject ID</th>
            <th>State</th>
            <th>Severity</th>
            <th>Isolation Mode</th>
            <th>Risk Score</th>
        </tr>
        {''.join(rows) or '<tr><td colspan="7">No containment cases yet.</td></tr>'}
    </table>
    """
    return _page("Contain Cases", body)


@app.get("/ops/contain/{case_id}", response_class=HTMLResponse)
def contain_case_detail(case_id: str) -> HTMLResponse:
    path = CONTAIN_DIR / f"{case_id}.json"
    if not path.exists():
        return _page("Contain Case Not Found", f"<h1>Contain case not found: {html.escape(case_id)}</h1>")

    data = json.loads(path.read_text(encoding="utf-8"))
    body = f"""
    <h1>Contain Case Detail</h1>
    <pre style="white-space: pre-wrap; word-wrap: break-word; border:1px solid #ddd; padding:16px; border-radius:12px;">{html.escape(json.dumps(data, indent=2))}</pre>
    """
    return _page("Contain Case Detail", body)


@app.get("/ops/deceive", response_class=HTMLResponse)
def deceive_cases() -> HTMLResponse:
    data = _load_json_files(DECEIVE_DIR)
    return _page("Deceive Cases", f"<pre>{html.escape(json.dumps(data, indent=2))}</pre>")


@app.get("/ops/honeypot", response_class=HTMLResponse)
def honeypot_cases() -> HTMLResponse:
    data = _load_json_files(HONEYPOT_DIR)
    return _page("Honeypot Cases", f"<pre>{html.escape(json.dumps(data, indent=2))}</pre>")


@app.get("/ops/minefield", response_class=HTMLResponse)
def minefield_cases() -> HTMLResponse:
    data = _load_json_files(MINEFIELD_DIR)
    return _page("Minefield Cases", f"<pre>{html.escape(json.dumps(data, indent=2))}</pre>")


@app.get("/ops/allow", response_class=HTMLResponse)
def allow_cases() -> HTMLResponse:
    data = _load_json_files(ALLOW_DIR)
    return _page("Allowed Submissions", f"<pre>{html.escape(json.dumps(data, indent=2))}</pre>")


@app.get("/ops/quarantine", response_class=HTMLResponse)
def legacy_quarantine() -> HTMLResponse:
    return contain_cases()
