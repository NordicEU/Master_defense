from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from shared.models.findings import AnalysisFinding, FindingSeverity

app = FastAPI(title="Context Validator", version="3.0.0")


class ContextRequest(BaseModel):
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)


KNOWN_EMPLOYMENT_RELATIONSHIPS = {
    ("11111111111", "999888777"),
    ("22222222222", "555444333"),
    ("33333333333", "123123123"),
    ("12345678901", "999888777"),
}

KNOWN_EMPLOYERS = {
    "999888777",
    "555444333",
    "123123123",
}

KNOWN_DOCUMENT_TYPES = {
    "OPPLYSNINGER_SKATTESUBJEKT_2025",
    "SALDO_RENTE",
    "SKATTEPLIKT_2025",
}

EXPECTED_CORE_FIELDS = {
    "OPPLYSNINGER_SKATTESUBJEKT_2025": {
        "skattemessig_bosatt",
        "behandlende_organisasjonsenhet",
        "skatteregnskapskommune",
        "kilde",
        "referanse",
    },
    "SALDO_RENTE": {
        "organisasjonsnummer",
        "organisasjonsnavn",
        "fornavn",
        "etternavn",
        "kontonummer",
        "kontotype",
        "utlaan",
        "innskudd",
        "opptjente_renter",
        "paaloepte_renter",
        "sum_innskudd",
        "sum_utlaan",
        "sum_opptjente_renter",
        "sum_paaloepte_renter",
    },
    "SKATTEPLIKT_2025": {
        "skatteplikt_til_norge",
        "tolvdel_ved_arbeidsopphold_i_norge",
        "alder_i_inntektsaar",
        "skattested",
        "skattested_i_tiltakssone",
    },
}


def add_finding(
    findings: List[AnalysisFinding],
    finding_type: str,
    severity: FindingSeverity,
    score: float,
    message: str,
    evidence: Dict[str, Any],
    rule_id: str,
) -> None:
    findings.append(
        AnalysisFinding(
            finding_type=finding_type,
            source_component="context_validator",
            severity=severity,
            score=score,
            message=message,
            evidence=evidence,
            rule_id=rule_id,
        )
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "context_validator"}


@app.post("/validate")
def validate_context(request: ContextRequest) -> Dict[str, Any]:
    payload = request.normalized_payload
    findings: List[AnalysisFinding] = []

    has_document_fields = isinstance(payload.get("fields"), dict) and payload.get("document_type") is not None

    if has_document_fields:
        document_type = payload.get("document_type")
        person_id = payload.get("person_id")
        partsnummer = payload.get("partsnummer")
        inntektsaar = payload.get("inntektsaar")
        fields = payload.get("fields", {})

        if document_type not in KNOWN_DOCUMENT_TYPES:
            add_finding(
                findings,
                "unknown_document_type",
                FindingSeverity.HIGH,
                0.72,
                message="Document type is not recognized in contextual reference set.",
                evidence={"document_type": document_type},
                rule_id="CTX_UNKNOWN_DOCUMENT_TYPE",
            )

        if not person_id:
            add_finding(
                findings,
                "missing_context_identifier",
                FindingSeverity.HIGH,
                0.70,
                message="Missing person identifier in document context.",
                evidence={"field": "person_id"},
                rule_id="CTX_MISSING_PERSON_ID",
            )

        if not partsnummer:
            add_finding(
                findings,
                "missing_context_identifier",
                FindingSeverity.MEDIUM,
                0.48,
                message="Missing partsnummer in document context.",
                evidence={"field": "partsnummer"},
                rule_id="CTX_MISSING_PARTSNUMMER",
            )

        if not inntektsaar:
            add_finding(
                findings,
                "missing_context_identifier",
                FindingSeverity.MEDIUM,
                0.48,
                message="Missing inntektsaar in document context.",
                evidence={"field": "inntektsaar"},
                rule_id="CTX_MISSING_INNTEKTSAAR",
            )

        expected_fields = EXPECTED_CORE_FIELDS.get(document_type, set())
        if expected_fields and isinstance(fields, dict):
            provided_fields = set(fields.keys())
            coverage = len(provided_fields & expected_fields) / max(len(expected_fields), 1)

            if coverage < 0.40:
                add_finding(
                    findings,
                    "document_context_mismatch",
                    FindingSeverity.HIGH,
                    0.72,
                    message="Document field coverage is far below the expected contextual structure.",
                    evidence={
                        "document_type": document_type,
                        "coverage": round(coverage, 4),
                        "expected_fields": sorted(expected_fields),
                        "provided_fields": sorted(provided_fields),
                    },
                    rule_id="CTX_DOCUMENT_FIELD_COVERAGE_LOW",
                )
            elif coverage < 0.75:
                add_finding(
                    findings,
                    "document_context_mismatch",
                    FindingSeverity.MEDIUM,
                    0.50,
                    message="Document field coverage is incomplete for the expected contextual structure.",
                    evidence={
                        "document_type": document_type,
                        "coverage": round(coverage, 4),
                        "expected_fields": sorted(expected_fields),
                        "provided_fields": sorted(provided_fields),
                    },
                    rule_id="CTX_DOCUMENT_FIELD_COVERAGE_MEDIUM",
                )

    else:
        person_id = str(payload.get("person_id") or "").strip()
        employer_id = str(payload.get("employer_id") or "").strip()

        if employer_id and employer_id not in KNOWN_EMPLOYERS:
            add_finding(
                findings,
                "unknown_employer",
                FindingSeverity.HIGH,
                0.82,
                message="Employer ID is not present in the contextual reference set.",
                evidence={"employer_id": employer_id},
                rule_id="CTX_UNKNOWN_EMPLOYER",
            )

        if person_id and employer_id:
            if (person_id, employer_id) not in KNOWN_EMPLOYMENT_RELATIONSHIPS:
                if employer_id in KNOWN_EMPLOYERS:
                    add_finding(
                        findings,
                        "context_mismatch",
                        FindingSeverity.HIGH,
                        0.84,
                        message="Employer relationship could not be verified for this person.",
                        evidence={
                            "person_id": person_id,
                            "employer_id": employer_id,
                        },
                        rule_id="CTX_EMPLOYMENT_RELATIONSHIP_MISMATCH",
                    )
                else:
                    add_finding(
                        findings,
                        "identity_mismatch",
                        FindingSeverity.HIGH,
                        0.88,
                        message="Person and employer combination is contextually inconsistent and unverified.",
                        evidence={
                            "person_id": person_id,
                            "employer_id": employer_id,
                        },
                        rule_id="CTX_IDENTITY_EMPLOYER_MISMATCH",
                    )

        if person_id and not employer_id:
            add_finding(
                findings,
                "missing_context_identifier",
                FindingSeverity.MEDIUM,
                0.46,
                message="Employer identifier is missing from the contextual relationship check.",
                evidence={"field": "employer_id"},
                rule_id="CTX_MISSING_EMPLOYER_ID",
            )

    if not findings:
        context_score = 0.10
    else:
        context_score = round(min(1.0, max(f.score for f in findings)), 4)

    return {
        "context_score": context_score,
        "findings": [f.model_dump(mode="json") for f in findings],
    }
