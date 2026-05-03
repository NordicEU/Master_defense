from __future__ import annotations

import html
import json
import os
import platform
import subprocess
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
BUSINESS_ACCEPTED_PATH = RUNTIME_DIR / "metrics" / "accepted_submissions.jsonl"

QUARANTINE_ADMIN_BASE = os.getenv("QUARANTINE_ADMIN_BASE", "http://127.0.0.1:8003")
MINEFIELD_BASE = os.getenv("MINEFIELD_BASE", "http://127.0.0.1:8006")

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


def _load_jsonl_file(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                if isinstance(data, dict):
                    items.append(data)
    except Exception:
        return []

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


def _get_json(url: str) -> Dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def _minefield_status_badge(status: str) -> str:
    status = _safe_str(status).lower()
    if status == "queued":
        return _badge("QUEUED", "#fef3c7", "#92400e")
    if status == "under_investigation":
        return _badge("UNDER_INVESTIGATION", "#dbeafe", "#1e3a8a")
    if status == "confirmed_hostile":
        return _badge("CONFIRMED_HOSTILE", "#fee2e2", "#991b1b")
    if status == "released":
        return _badge("RELEASED", "#dcfce7", "#166534")
    return _badge(status.upper() or "UNKNOWN")


def _build_trace_command(target: str) -> List[str]:
    if platform.system().lower() == "windows":
        return ["tracert", "-d", target]
    return ["traceroute", "-n", target]


def _run_trace_target(target: str) -> Dict[str, Any]:
    command = _build_trace_command(target)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return {
            "command": " ".join(command),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except Exception as exc:
        return {
            "command": " ".join(command),
            "stdout": "",
            "stderr": str(exc),
            "returncode": 1,
        }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "ops_app"}


@app.get("/ops", response_class=HTMLResponse)
def ops_overview() -> HTMLResponse:
    contain_cases = [item for item in _load_json_files(CONTAIN_DIR) if isinstance(item, dict) and "case_id" in item]
    deceive_cases = _load_json_files(DECEIVE_DIR)
    honeypot_cases = _load_json_files(HONEYPOT_DIR)
    minefield_cases = _load_json_files(MINEFIELD_DIR)
    allow_cases = _load_jsonl_file(BUSINESS_ACCEPTED_PATH)
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
        {_metric_card("Accepted requests", len(allow_cases))}
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
    data = _get_json(f"{MINEFIELD_BASE}/defer/summaries/list").get("cases", [])
    data = data if isinstance(data, list) else []

    rows = []
    for case in data:
        defer_id = _safe_str(case.get("defer_id", "unknown"))
        submission_id = _safe_str(case.get("submission_id", "unknown"))
        subject_id = _safe_str(case.get("subject_id", "-"))
        request_ip = _safe_str(case.get("request_ip", "-")) or "-"
        status = _safe_str(case.get("status", "queued"))
        risk_score = case.get("risk_score", "n/a")
        resolution_reason = _safe_str(case.get("resolution_reason", "")) or "-"
        note_count = case.get("analyst_note_count", 0)
        rows.append(
            f"""
            <tr>
                <td><a href="/ops/minefield/{html.escape(defer_id)}">{html.escape(defer_id)}</a></td>
                <td>{html.escape(submission_id)}</td>
                <td>{html.escape(subject_id)}</td>
                <td>{html.escape(request_ip)}</td>
                <td>{_minefield_status_badge(status)}</td>
                <td>{html.escape(str(risk_score))}</td>
                <td>{html.escape(str(note_count))}</td>
                <td>{html.escape(resolution_reason)}</td>
            </tr>
            """
        )

    body = f"""
    <h1>Minefield Cases</h1>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th>Minefield ID</th>
            <th>Submission ID</th>
            <th>Subject ID</th>
            <th>Request IP</th>
            <th>Status</th>
            <th>Risk Score</th>
            <th>Notes</th>
            <th>Resolution</th>
        </tr>
        {''.join(rows) or '<tr><td colspan="8">No minefield cases yet.</td></tr>'}
    </table>
    """
    return _page("Minefield Cases", body)


@app.get("/ops/minefield/{defer_id}", response_class=HTMLResponse)
def minefield_case_detail(defer_id: str) -> HTMLResponse:
    data = _get_json(f"{MINEFIELD_BASE}/defer/{defer_id}")
    status = _safe_str(data.get("status", "queued"))
    submission = data.get("submission", {})
    normalized_payload = data.get("normalized_payload", {})
    notes = data.get("analyst_notes", [])
    notes = notes if isinstance(notes, list) else []
    minefield_controls = data.get("minefield_controls", {})
    behavior_capture = minefield_controls.get("behavior_capture", {})
    link_analysis = minefield_controls.get("link_analysis", {})
    progressive_delay = minefield_controls.get("progressive_delay", {})
    trace_runs = data.get("trace_runs", [])
    trace_runs = trace_runs if isinstance(trace_runs, list) else []

    note_rows = []
    for note in notes:
        note_rows.append(
            f"""
            <tr>
                <td>{html.escape(_safe_str(note.get("timestamp")) or "-")}</td>
                <td>{html.escape(_safe_str(note.get("actor")) or "-")}</td>
                <td>{html.escape(_safe_str(note.get("event")) or "-")}</td>
                <td>{html.escape(_safe_str(note.get("note")) or "-")}</td>
            </tr>
            """
        )

    trace_rows = []
    for trace in trace_runs:
        trace_rows.append(
            f"""
            <tr>
                <td>{html.escape(_safe_str(trace.get("timestamp")) or "-")}</td>
                <td>{html.escape(_safe_str(trace.get("actor")) or "-")}</td>
                <td>{html.escape(_safe_str(trace.get("target")) or "-")}</td>
                <td>{html.escape(_safe_str(trace.get("command")) or "-")}</td>
                <td>{html.escape(str(trace.get("returncode", "-")))}</td>
            </tr>
            """
        )

    body = f"""
    <h1>Minefield Case Detail</h1>
    <div style="border:1px solid #ddd;padding:16px;border-radius:12px;">
        <p><strong>Minefield ID:</strong> {html.escape(defer_id)}</p>
        <p><strong>Status:</strong> {_minefield_status_badge(status)}</p>
        <p><strong>Submission ID:</strong> {html.escape(_safe_str(submission.get("submission_id")) or "-")}</p>
        <p><strong>Subject ID:</strong> {html.escape(_safe_str(normalized_payload.get("person_id")) or "-")}</p>
        <p><strong>Request IP:</strong> {html.escape(_safe_str(submission.get("request_ip")) or "-")}</p>
        <p><strong>Risk Score:</strong> {html.escape(str(data.get("risk_assessment", {}).get("total_score", "n/a")))}</p>
        <p><strong>Resolution Reason:</strong> {html.escape(_safe_str(data.get("resolution_reason")) or "-")}</p>
        <p><strong>Updated At:</strong> {html.escape(_safe_str(data.get("updated_at")) or "-")}</p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:24px;align-items:start;">
        <form method="post" action="/ops/minefield/{html.escape(defer_id)}/status" style="border:1px solid #ddd;padding:16px;border-radius:12px;">
            <h3 style="margin-top:0;">Update Status</h3>
            <input type="hidden" name="actor" value="minefield_operator">
            <label>Status<br>
                <select name="status" style="width:100%;padding:10px;margin-top:6px;">
                    <option value="queued">queued</option>
                    <option value="under_investigation">under_investigation</option>
                    <option value="confirmed_hostile">confirmed_hostile</option>
                    <option value="released">released</option>
                </select>
            </label>
            <label style="display:block;margin-top:12px;">Resolution reason<br>
                <input type="text" name="resolution_reason" style="width:100%;padding:10px;margin-top:6px;">
            </label>
            <label style="display:block;margin-top:12px;">Note<br>
                <textarea name="note" rows="4" style="width:100%;padding:10px;margin-top:6px;"></textarea>
            </label>
            <button type="submit" style="padding:10px 14px;margin-top:12px;">Save Status</button>
        </form>
        <form method="post" action="/ops/minefield/{html.escape(defer_id)}/notes" style="border:1px solid #ddd;padding:16px;border-radius:12px;">
            <h3 style="margin-top:0;">Add Analyst Note</h3>
            <input type="hidden" name="actor" value="minefield_operator">
            <label>Note<br>
                <textarea name="note" rows="6" style="width:100%;padding:10px;margin-top:6px;" required></textarea>
            </label>
            <button type="submit" style="padding:10px 14px;margin-top:12px;">Add Note</button>
        </form>
    </div>
    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:12px;">
        <h3 style="margin-top:0;">Run Trace</h3>
        <p style="margin-top:0;color:#4b5563;">Run a trace from the ops host and store the result on this minefield case.</p>
        <form method="post" action="/ops/minefield/{html.escape(defer_id)}/trace">
            <input type="hidden" name="actor" value="minefield_operator">
            <label>Target host or IP<br>
                <input
                    type="text"
                    name="target"
                    placeholder="8.8.8.8"
                    style="width:100%;padding:10px;margin-top:6px;"
                    required
                >
            </label>
            <button type="submit" style="padding:10px 14px;margin-top:12px;">Run Trace</button>
        </form>
    </div>
    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:12px;">
        <h3>Controls Summary</h3>
        <p><strong>Progressive delay:</strong> {html.escape(_safe_str(progressive_delay.get("status")) or "-")}</p>
        <p><strong>Delay tier:</strong> {html.escape(_safe_str(progressive_delay.get("delay_tier")) or "-")}</p>
        <p><strong>Recommended delay seconds:</strong> {html.escape(str(progressive_delay.get("recommended_delay_seconds", "n/a")))}</p>
        <p><strong>Delay reasons:</strong> {html.escape(", ".join(progressive_delay.get("reasons", [])) or "-")}</p>
        <p><strong>Behavior capture:</strong> {html.escape(_safe_str(behavior_capture.get("status")) or "-")}</p>
        <p><strong>Prior same subject cases:</strong> {html.escape(str(behavior_capture.get("prior_same_subject_cases", "n/a")))}</p>
        <p><strong>Prior same employer cases:</strong> {html.escape(str(behavior_capture.get("prior_same_employer_cases", "n/a")))}</p>
        <p><strong>Recent related case IDs:</strong> {html.escape(", ".join(behavior_capture.get("recent_related_case_ids", [])) or "-")}</p>
        <p><strong>Link analysis:</strong> {html.escape(_safe_str(link_analysis.get("status")) or "-")}</p>
        <p><strong>Related case count:</strong> {html.escape(str(link_analysis.get("related_case_count", "n/a")))}</p>
        <p><strong>Relation counts:</strong> {html.escape(json.dumps(link_analysis.get("relation_counts", {})))}</p>
        <p><strong>Trace runs stored:</strong> {html.escape(str(len(trace_runs)))}</p>
        <p style="margin-top:12px;"><strong>Manual trace script example:</strong> <code>py scripts/analyst_trace_target.py --case-id {html.escape(defer_id)} --target 8.8.8.8</code></p>
    </div>
    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:12px;">
        <h3>Analyst Notes</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>Timestamp</th>
                <th>Actor</th>
                <th>Event</th>
                <th>Note</th>
            </tr>
            {''.join(note_rows) or '<tr><td colspan="4">No analyst notes yet.</td></tr>'}
        </table>
    </div>
    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:12px;">
        <h3>Trace Runs</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>Timestamp</th>
                <th>Actor</th>
                <th>Target</th>
                <th>Command</th>
                <th>Return Code</th>
            </tr>
            {''.join(trace_rows) or '<tr><td colspan="5">No trace runs stored yet.</td></tr>'}
        </table>
    </div>
    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:12px;">
        <h3>Full Minefield JSON</h3>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">{html.escape(json.dumps(data, indent=2))}</pre>
    </div>
    """
    return _page("Minefield Case Detail", body)


@app.post("/ops/minefield/{defer_id}/status")
def ops_minefield_status_update(
    defer_id: str,
    status: str = Form(...),
    actor: str = Form("minefield_operator"),
    note: str = Form(""),
    resolution_reason: str = Form(""),
) -> RedirectResponse:
    payload = {
        "actor": actor,
        "status": status,
        "note": note or None,
        "resolution_reason": resolution_reason or None,
    }
    _post_json(f"{MINEFIELD_BASE}/defer/{defer_id}/status", payload)
    return RedirectResponse(url=f"/ops/minefield/{defer_id}", status_code=303)


@app.post("/ops/minefield/{defer_id}/notes")
def ops_minefield_add_note(
    defer_id: str,
    actor: str = Form("minefield_operator"),
    note: str = Form(...),
) -> RedirectResponse:
    _post_json(
        f"{MINEFIELD_BASE}/defer/{defer_id}/notes",
        {
            "actor": actor,
            "note": note,
        },
    )
    return RedirectResponse(url=f"/ops/minefield/{defer_id}", status_code=303)


@app.post("/ops/minefield/{defer_id}/trace")
def ops_minefield_run_trace(
    defer_id: str,
    actor: str = Form("minefield_operator"),
    target: str = Form(...),
) -> RedirectResponse:
    cleaned_target = _safe_str(target)
    if cleaned_target:
        trace_result = _run_trace_target(cleaned_target)
        _post_json(
            f"{MINEFIELD_BASE}/defer/{defer_id}/trace-results",
            {
                "actor": actor,
                "target": cleaned_target,
                "command": trace_result["command"],
                "stdout": trace_result["stdout"],
                "stderr": trace_result["stderr"],
                "returncode": trace_result["returncode"],
            },
        )
    return RedirectResponse(url=f"/ops/minefield/{defer_id}", status_code=303)


@app.get("/ops/allow", response_class=HTMLResponse)
def allow_cases() -> HTMLResponse:
    data = _load_jsonl_file(BUSINESS_ACCEPTED_PATH)
    return _page("Accepted Requests", f"<pre>{html.escape(json.dumps(data, indent=2))}</pre>")


@app.get("/ops/quarantine", response_class=HTMLResponse)
def legacy_quarantine() -> HTMLResponse:
    return contain_cases()
