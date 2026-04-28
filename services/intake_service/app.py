from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from shared.models.submission import Submission, SubmissionPayload

app = FastAPI(title="Intake Service", version="2.0.0")


class IntakeRequest(BaseModel):
    source: str = "web_form"
    payload_type: str = "tax_declaration"
    correlation_id: str | None = None
    schema_version: str = "v1"
    payload: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "intake_service"}


@app.post("/intake")
def intake_submission(request: IntakeRequest) -> Dict[str, Any]:
    submission = Submission(
        source=request.source,
        payload_type=request.payload_type,
        correlation_id=request.correlation_id,
        schema_version=request.schema_version,
        payload=SubmissionPayload(data=request.payload),
    )

    payload = request.payload

    # Document-based replay path
    if isinstance(payload.get("fields"), dict) and payload.get("document_type") is not None:
        normalized_payload = {
            "document_type": payload.get("document_type"),
            "person_id": payload.get("person_id"),
            "partsnummer": payload.get("partsnummer"),
            "inntektsaar": payload.get("inntektsaar"),
            "fields": payload.get("fields", {}),
            "raw_payload_keys": sorted(list(payload.keys())),
        }
    else:
        # Original web-form path
        normalized_payload = {
            "person_id": payload.get("person_id"),
            "employer_id": payload.get("employer_id"),
            "declared_income": payload.get("declared_income"),
            "declared_expenses": payload.get("declared_expenses"),
            "employment_start": payload.get("employment_start"),
            "employment_end": payload.get("employment_end"),
            "raw_payload_keys": sorted(list(payload.keys())),
        }

    return {
        "submission": submission.model_dump(mode="json"),
        "normalized_payload": normalized_payload,
    }
