from __future__ import annotations

import html
import json
import os
import random
from typing import Any, Dict, List
from uuid import uuid4

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from apps.input_app.thesis_generation import build_generated_gateway_payload

app = FastAPI(title="Tax Submission Input App", version="6.0.0")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000/route")
SUBJECT_CONTROL_URL = os.getenv("SUBJECT_CONTROL_URL", "http://127.0.0.1:8003/subjects")


def _no_store(response: HTMLResponse) -> HTMLResponse:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _page(title: str, body: str) -> HTMLResponse:
    response = HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{html.escape(title)}</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 960px; margin: 40px auto; padding: 20px; line-height: 1.5;">
            {body}
        </body>
        </html>
        """
    )
    return _no_store(response)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _extract_request_ip(request: Request) -> str:
    forwarded_for = _safe_str(request.headers.get("x-forwarded-for"))
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = _safe_str(request.headers.get("x-real-ip"))
    if real_ip:
        return real_ip

    if request.client and request.client.host:
        return _safe_str(request.client.host)

    return "unknown"


def _get_subject_control(subject_id: str) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{SUBJECT_CONTROL_URL}/{subject_id}")
            response.raise_for_status()
            return response.json()
    except Exception:
        return {
            "subject_id": subject_id,
            "state": "NORMAL",
            "reason": "",
            "linked_case_ids": [],
        }


def _render_input_form() -> HTMLResponse:
    body = """
    <h1>Tax Submission Input App</h1>
    <p>
        Submit a tax declaration and let the embedded defense layer decide whether the claim
        should be accepted, contained, or routed elsewhere.
    </p>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start;margin-top:24px;">
    <section>
    <h2>Manual Submission</h2>
    <form method="post" action="/submit" style="display:grid; gap:14px; max-width:560px; margin-top:24px;">
        <label>
            Person ID<br>
            <input type="text" name="person_id" required style="width:100%; padding:10px;">
        </label>

        <label>
            Employer ID<br>
            <input type="text" name="employer_id" required style="width:100%; padding:10px;">
        </label>

        <label>
            Declared Income<br>
            <input type="number" step="0.01" name="declared_income" required style="width:100%; padding:10px;">
        </label>

        <label>
            Declared Expenses<br>
            <input type="number" step="0.01" name="declared_expenses" required style="width:100%; padding:10px;">
        </label>

        <label>
            Employment Start<br>
            <input type="text" name="employment_start" placeholder="01.01.2026" required style="width:100%; padding:10px;">
        </label>

        <label>
            Employment End<br>
            <input type="text" name="employment_end" placeholder="31.12.2026" required style="width:100%; padding:10px;">
        </label>

        <button type="submit" style="padding:12px 18px; font-size:16px;">Submit Tax Declaration</button>
    </form>
    </section>

    <section>
    <h2>Generated Requests</h2>
    <form method="post" action="/generate-requests" style="display:grid; gap:14px; max-width:560px; margin-top:24px;">
        <label>
            Number of requests<br>
            <input type="number" name="count" min="1" max="100" value="10" required style="width:100%; padding:10px;">
        </label>

        <label>
            Dataset mix<br>
            <select name="sample_mode" style="width:100%; padding:10px;">
                <option value="mixed">Mixed green/adversarial</option>
                <option value="green">Green only</option>
                <option value="adversarial">Adversarial only</option>
            </select>
        </label>

        <label>
            Adversarial generator<br>
            <select name="adversarial_engine" style="width:100%; padding:10px;">
                <option value="fallback">Fast thesis fallback mutation</option>
                <option value="llm">Ollama/Llama thesis generator</option>
            </select>
        </label>

        <button type="submit" style="padding:12px 18px; font-size:16px;">Send Generated Requests</button>
    </form>
    </section>
    </div>
    """
    return _page("Tax Submission Input App", body)


def _render_subject_locked(subject_control: Dict[str, Any]) -> HTMLResponse:
    state = html.escape(_safe_str(subject_control.get("state", "UNKNOWN")))
    reason = html.escape(_safe_str(subject_control.get("reason", "")))
    linked_case_ids = subject_control.get("linked_case_ids", [])
    linked_case_ids = linked_case_ids if isinstance(linked_case_ids, list) else []
    linked_case_html = "<br>".join(html.escape(str(x)) for x in linked_case_ids) if linked_case_ids else "None"

    body = f"""
    <h1>Submission Access Restricted</h1>
    <p>
        This subject is currently under containment control. New submissions are temporarily blocked
        until the case is released or reset by an operator.
    </p>

    <div style="border:1px solid #ddd;padding:16px;border-radius:10px;max-width:760px;background:#fff7ed;">
        <p><strong>State:</strong> {state}</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p><strong>Linked case IDs:</strong><br>{linked_case_html}</p>
    </div>

    <p style="margin-top:20px;">
        Refreshing the page or using the browser back button will not restore normal submission access
        while this subject remains restricted or blocked.
    </p>
    """
    return _page("Submission Access Restricted", body)


def _build_submission(
    person_id: str,
    employer_id: str,
    declared_income: float,
    declared_expenses: float,
    employment_start: str,
    employment_end: str,
    source: str = "input_app",
    request_ip: str | None = None,
) -> Dict[str, Any]:
    submission_id = str(uuid4())
    return {
        "submission_id": submission_id,
        "person_id": person_id,
        "employer_id": employer_id,
        "declared_income": declared_income,
        "declared_expenses": declared_expenses,
        "employment_start": employment_start,
        "employment_end": employment_end,
        "source": source,
        "request_ip": _safe_str(request_ip) or "unknown",
    }


def _build_normalized_payload(
    person_id: str,
    employer_id: str,
    declared_income: float,
    declared_expenses: float,
    employment_start: str,
    employment_end: str,
) -> Dict[str, Any]:
    return {
        "person_id": person_id,
        "employer_id": employer_id,
        "declared_income": declared_income,
        "declared_expenses": declared_expenses,
        "employment_start": employment_start,
        "employment_end": employment_end,
    }


def build_submission_payload(
    person_id: str,
    employer_id: str,
    declared_income: float,
    declared_expenses: float,
    employment_start: str,
    employment_end: str,
    source: str = "input_app",
    request_ip: str | None = None,
) -> Dict[str, Any]:
    return {
        "submission": _build_submission(
            person_id=person_id,
            employer_id=employer_id,
            declared_income=declared_income,
            declared_expenses=declared_expenses,
            employment_start=employment_start,
            employment_end=employment_end,
            source=source,
            request_ip=request_ip,
        ),
        "normalized_payload": _build_normalized_payload(
            person_id=person_id,
            employer_id=employer_id,
            declared_income=declared_income,
            declared_expenses=declared_expenses,
            employment_start=employment_start,
            employment_end=employment_end,
        ),
    }


def _post_gateway_payload(payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(GATEWAY_URL, json=payload)
        response.raise_for_status()
        return response.json()


def _result_heading(flow_result: str) -> str:
    mapping = {
        "ALLOW": "Submission Accepted",
        "CONTAIN": "Submission Routed to Containment",
        "HONEYPOT": "Submission Routed to Honeypot",
        "DECEIVE": "Submission Routed to Deceiver",
        "MINEFIELD": "Submission Routed to Minefield",
    }
    return mapping.get(flow_result, "Submission Result")


def _result_summary(flow_result: str, action: str) -> str:
    if flow_result == "ALLOW":
        return "The submission was assessed as low enough risk to continue into the business flow."
    if flow_result == "CONTAIN":
        return "The submission was judged suspicious enough to be held inside containment."
    if flow_result == "HONEYPOT":
        return "The submission was redirected to a honeypot path."
    if flow_result == "DECEIVE":
        return "The submission was redirected to a deception path."
    if flow_result == "MINEFIELD":
        return "The submission was escalated to minefield handling."
    return f"The gateway selected defense action {action}."


def _render_risk_summary(risk_assessment: Dict[str, Any]) -> str:
    total_score = risk_assessment.get("total_score", "n/a")
    confidence = risk_assessment.get("confidence", "n/a")
    recommended_action = _safe_str(risk_assessment.get("recommended_action", ""))
    semantic_reasoning = _safe_str(risk_assessment.get("semantic_reasoning", ""))
    finding_types = risk_assessment.get("finding_types", [])
    if not isinstance(finding_types, list):
        finding_types = []

    finding_html = ", ".join(html.escape(str(x)) for x in finding_types[:8]) if finding_types else "None"

    return f"""
    <div style="border:1px solid #ddd;padding:16px;border-radius:10px;">
        <h3>Risk Summary</h3>
        <p><strong>Total score:</strong> {html.escape(str(total_score))}</p>
        <p><strong>Confidence:</strong> {html.escape(str(confidence))}</p>
        <p><strong>Recommended action:</strong> {html.escape(recommended_action or "n/a")}</p>
        <p><strong>Finding types:</strong> {finding_html}</p>
        <p><strong>Reasoning:</strong> {html.escape(semantic_reasoning or "No summary available.")}</p>
    </div>
    """


def _render_route_summary(result: Dict[str, Any]) -> str:
    action = _safe_str(result.get("action", "UNKNOWN"))
    handoff = _safe_str(result.get("handoff", "UNKNOWN"))
    flow_result = _safe_str(result.get("flow_result", "UNKNOWN"))
    submission_id = _safe_str(result.get("submission_id", "unknown"))

    downstream_response = result.get("downstream_response", {})
    case_or_token = "unknown"
    if isinstance(downstream_response, dict):
        case_or_token = _safe_str(
            downstream_response.get("case_id")
            or downstream_response.get("submission_id")
            or downstream_response.get("deception_id")
            or downstream_response.get("review_id")
            or downstream_response.get("defer_id")
            or "unknown"
        )

    summary = _result_summary(flow_result, action)

    return f"""
    <div style="border:1px solid #ddd;padding:16px;border-radius:10px;">
        <h3>Routing Summary</h3>
        <p>{html.escape(summary)}</p>
        <p><strong>Submission ID:</strong> {html.escape(submission_id)}</p>
        <p><strong>Flow result:</strong> {html.escape(flow_result)}</p>
        <p><strong>Defense action:</strong> {html.escape(action)}</p>
        <p><strong>Handoff:</strong> {html.escape(handoff)}</p>
        <p><strong>Case / token:</strong> {html.escape(case_or_token)}</p>
    </div>
    """


def _render_result_page(result: Dict[str, Any]) -> str:
    action = _safe_str(result.get("action", "UNKNOWN"))
    flow_result = _safe_str(result.get("flow_result", "UNKNOWN"))
    title = _result_heading(flow_result)
    risk_assessment = result.get("risk_assessment", {})
    risk_assessment = risk_assessment if isinstance(risk_assessment, dict) else {}

    raw_response = html.escape(json.dumps(result, indent=2, ensure_ascii=False))

    return f"""
    <a href="/" style="display:inline-block;margin-bottom:20px;">&#8592; Return</a>

    <h1>{html.escape(title)}</h1>
    <p style="font-size:24px;margin-bottom:24px;">
        Defense action selected: <strong>{html.escape(action)}</strong>
    </p>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;">
        {_render_route_summary(result)}
        {_render_risk_summary(risk_assessment)}
    </div>

    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:10px;">
        <h3>Full Gateway Response</h3>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">{raw_response}</pre>
    </div>
    """


def _select_generated_kind(sample_mode: str) -> str:
    sample_mode = _safe_str(sample_mode).lower()
    if sample_mode == "green":
        return "green"
    if sample_mode == "adversarial":
        return "adversarial"
    return "adversarial" if random.random() < 0.30 else "green"


def _render_generated_results(results: List[Dict[str, Any]]) -> HTMLResponse:
    counts: Dict[str, int] = {}
    rows = []

    for index, item in enumerate(results, start=1):
        action = _safe_str(item.get("action", "ERROR"))
        counts[action] = counts.get(action, 0) + 1
        risk_score = item.get("risk_score", "n/a")
        sample_kind = _safe_str(item.get("sample_kind", "unknown"))
        submission_id = _safe_str(item.get("submission_id", "unknown"))
        source_file = _safe_str(item.get("source_file", "unknown"))
        error = _safe_str(item.get("error", ""))

        rows.append(
            f"""
            <tr>
                <td>{index}</td>
                <td>{html.escape(sample_kind)}</td>
                <td>{html.escape(action)}</td>
                <td>{html.escape(str(risk_score))}</td>
                <td>{html.escape(submission_id)}</td>
                <td>{html.escape(source_file)}</td>
                <td>{html.escape(error)}</td>
            </tr>
            """
        )

    count_html = "".join(
        f"<li><strong>{html.escape(action)}:</strong> {count}</li>"
        for action, count in sorted(counts.items())
    )
    raw_response = html.escape(json.dumps(results, indent=2, ensure_ascii=False))

    body = f"""
    <a href="/" style="display:inline-block;margin-bottom:20px;">&#8592; Return</a>
    <h1>Generated Request Results</h1>
    <ul>{count_html}</ul>

    <table style="width:100%;border-collapse:collapse;margin-top:20px;">
        <thead>
            <tr>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">#</th>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">Kind</th>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">Action</th>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">Risk</th>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">Submission</th>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">Source XML</th>
                <th style="text-align:left;border-bottom:1px solid #ddd;padding:8px;">Error</th>
            </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
    </table>

    <div style="margin-top:24px;border:1px solid #ddd;padding:16px;border-radius:10px;">
        <h3>Full Batch Response</h3>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">{raw_response}</pre>
    </div>
    """
    return _page("Generated Request Results", body)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    locked_subject = request.cookies.get("subject_lock")

    if locked_subject:
        subject_control = _get_subject_control(locked_subject)
        state = _safe_str(subject_control.get("state", "NORMAL")).upper()

        if state in {"RESTRICTED", "BLOCKED"}:
            return _render_subject_locked(subject_control)

    return _render_input_form()


@app.post("/submit", response_class=HTMLResponse)
def submit(
    request: Request,
    person_id: str = Form(...),
    employer_id: str = Form(...),
    declared_income: float = Form(...),
    declared_expenses: float = Form(...),
    employment_start: str = Form(...),
    employment_end: str = Form(...),
) -> HTMLResponse:
    subject_control = _get_subject_control(person_id)
    current_state = _safe_str(subject_control.get("state", "NORMAL")).upper()

    if current_state in {"RESTRICTED", "BLOCKED"}:
        page = _render_subject_locked(subject_control)
        page.set_cookie(
            key="subject_lock",
            value=str(person_id),
            httponly=True,
            samesite="Lax",
            max_age=86400,
        )
        return page

    payload = build_submission_payload(
        person_id=person_id,
        employer_id=employer_id,
        declared_income=declared_income,
        declared_expenses=declared_expenses,
        employment_start=employment_start,
        employment_end=employment_end,
        request_ip=_extract_request_ip(request),
    )

    try:
        result = _post_gateway_payload(payload)
    except Exception as exc:
        return _page(
            "Submission Failed",
            f"""
            <h1>Submission Failed</h1>
            <p>The request could not be processed.</p>
            <pre>{html.escape(str(exc))}</pre>
            <p><a href="/">Back to input form</a></p>
            """,
        )

    page_html = _render_result_page(result)
    page = _page("Submission Result", page_html)

    action = _safe_str(result.get("action", "")).upper()
    if action in {"CONTAIN", "MINEFIELD", "HONEYPOT", "DECEIVE"}:
        page.set_cookie(
            key="subject_lock",
            value=str(person_id),
            httponly=True,
            samesite="Lax",
            max_age=86400,
        )
    elif action == "ALLOW":
        page.delete_cookie("subject_lock")

    return page


@app.post("/generate-requests", response_class=HTMLResponse)
def generate_requests(
    request: Request,
    count: int = Form(10),
    sample_mode: str = Form("mixed"),
    adversarial_engine: str = Form("fallback"),
) -> HTMLResponse:
    count = max(1, min(int(count), 100))
    use_llm_adversary = _safe_str(adversarial_engine).lower() == "llm"
    request_ip = _extract_request_ip(request)
    results: List[Dict[str, Any]] = []

    for _ in range(count):
        sample_kind = _select_generated_kind(sample_mode)
        try:
            generated = build_generated_gateway_payload(
                sample_kind=sample_kind,
                use_llm_adversary=use_llm_adversary,
            )
            generated["submission"]["request_ip"] = request_ip
            payload = {
                "submission": generated["submission"],
                "normalized_payload": generated["normalized_payload"],
            }
            response = _post_gateway_payload(payload, timeout=120.0 if use_llm_adversary else 60.0)
            risk_assessment = response.get("risk_assessment", {})
            risk_assessment = risk_assessment if isinstance(risk_assessment, dict) else {}

            results.append(
                {
                    "sample_kind": sample_kind,
                    "submission_id": generated["submission"].get("submission_id"),
                    "source_file": generated["submission"].get("source_file"),
                    "action": response.get("action"),
                    "flow_result": response.get("flow_result"),
                    "handoff": response.get("handoff"),
                    "risk_score": risk_assessment.get("total_score"),
                    "gateway_response": response,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "sample_kind": sample_kind,
                    "action": "ERROR",
                    "error": str(exc),
                }
            )

    return _render_generated_results(results)


@app.post("/generate-requests/json")
def generate_requests_json(
    request: Request,
    count: int = 10,
    sample_mode: str = "mixed",
    adversarial_engine: str = "fallback",
) -> Dict[str, Any]:
    count = max(1, min(int(count), 100))
    use_llm_adversary = _safe_str(adversarial_engine).lower() == "llm"
    request_ip = _extract_request_ip(request)
    results: List[Dict[str, Any]] = []

    for _ in range(count):
        sample_kind = _select_generated_kind(sample_mode)
        generated = build_generated_gateway_payload(
            sample_kind=sample_kind,
            use_llm_adversary=use_llm_adversary,
        )
        generated["submission"]["request_ip"] = request_ip
        payload = {
            "submission": generated["submission"],
            "normalized_payload": generated["normalized_payload"],
        }
        response = _post_gateway_payload(payload, timeout=120.0 if use_llm_adversary else 60.0)
        results.append(
            {
                "sample_kind": sample_kind,
                "submission": generated["submission"],
                "normalized_payload": generated["normalized_payload"],
                "thesis_sample": generated["thesis_sample"],
                "gateway_response": response,
            }
        )

    return {
        "count": len(results),
        "sample_mode": sample_mode,
        "adversarial_engine": adversarial_engine,
        "results": results,
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "input_app"}
