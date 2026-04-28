from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from shared.models.findings import AnalysisFinding, FindingSeverity

app = FastAPI(title="Rule Engine", version="3.0.0")


class RuleRequest(BaseModel):
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)


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
            source_component="rule_engine",
            severity=severity,
            score=score,
            message=message,
            evidence=evidence,
            rule_id=rule_id,
        )
    )


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "rule_engine"}


@app.post("/analyze")
def analyze_rules(request: RuleRequest) -> Dict[str, Any]:
    payload = request.normalized_payload
    findings: List[AnalysisFinding] = []

    has_document_fields = isinstance(payload.get("fields"), dict) and payload.get("document_type") is not None

    if has_document_fields:
        document_type = payload.get("document_type")
        person_id = payload.get("person_id")
        partsnummer = payload.get("partsnummer")
        inntektsaar = payload.get("inntektsaar")
        fields = payload.get("fields", {})

        if not document_type:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.HIGH,
                score=0.80,
                message="Missing document_type.",
                evidence={"field": "document_type"},
                rule_id="RULE_MISSING_DOCUMENT_TYPE",
            )

        if not person_id:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.HIGH,
                score=0.80,
                message="Missing person_id.",
                evidence={"field": "person_id"},
                rule_id="RULE_MISSING_PERSON_ID",
            )

        if not partsnummer:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.MEDIUM,
                score=0.55,
                message="Missing partsnummer.",
                evidence={"field": "partsnummer"},
                rule_id="RULE_MISSING_PARTSNUMMER",
            )

        if not inntektsaar:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.MEDIUM,
                score=0.55,
                message="Missing inntektsaar.",
                evidence={"field": "inntektsaar"},
                rule_id="RULE_MISSING_INNTEKTSAAR",
            )

        if not isinstance(fields, dict) or not fields:
            add_finding(
                findings,
                finding_type="missing_field_group",
                severity=FindingSeverity.HIGH,
                score=0.78,
                message="Missing or empty fields payload.",
                evidence={"field": "fields"},
                rule_id="RULE_EMPTY_FIELDS_OBJECT",
            )

        if isinstance(inntektsaar, str) and not inntektsaar.isdigit():
            add_finding(
                findings,
                finding_type="format_inconsistency",
                severity=FindingSeverity.MEDIUM,
                score=0.46,
                message="inntektsaar should be numeric string.",
                evidence={"inntektsaar": inntektsaar},
                rule_id="RULE_BAD_INNTEKTSAAR_FORMAT",
            )

    else:
        person_id = payload.get("person_id")
        employer_id = payload.get("employer_id")
        declared_income = _safe_float(payload.get("declared_income"))
        declared_expenses = _safe_float(payload.get("declared_expenses"))
        employment_start = str(payload.get("employment_start") or "").strip()
        employment_end = str(payload.get("employment_end") or "").strip()

        if not person_id:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.HIGH,
                score=0.85,
                message="Missing person_id.",
                evidence={"field": "person_id"},
                rule_id="RULE_MISSING_PERSON_ID",
            )

        if not employer_id:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.HIGH,
                score=0.85,
                message="Missing employer_id.",
                evidence={"field": "employer_id"},
                rule_id="RULE_MISSING_EMPLOYER_ID",
            )

        if declared_income is None:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.MEDIUM,
                score=0.60,
                message="Missing declared_income.",
                evidence={"field": "declared_income"},
                rule_id="RULE_MISSING_DECLARED_INCOME",
            )

        if declared_expenses is None:
            add_finding(
                findings,
                finding_type="missing_field",
                severity=FindingSeverity.MEDIUM,
                score=0.55,
                message="Missing declared_expenses.",
                evidence={"field": "declared_expenses"},
                rule_id="RULE_MISSING_DECLARED_EXPENSES",
            )

        if declared_income is not None and declared_income < 0:
            add_finding(
                findings,
                finding_type="invalid_income",
                severity=FindingSeverity.HIGH,
                score=0.92,
                message="Declared income cannot be negative.",
                evidence={"declared_income": declared_income},
                rule_id="RULE_NEGATIVE_DECLARED_INCOME",
            )

        if declared_expenses is not None and declared_expenses < 0:
            add_finding(
                findings,
                finding_type="negative_expenses",
                severity=FindingSeverity.HIGH,
                score=0.90,
                message="Declared expenses cannot be negative.",
                evidence={"declared_expenses": declared_expenses},
                rule_id="RULE_NEGATIVE_DECLARED_EXPENSES",
            )

        if (
            declared_income is not None
            and declared_expenses is not None
            and declared_income >= 0
            and declared_expenses >= 0
        ):
            if declared_expenses > declared_income:
                add_finding(
                    findings,
                    finding_type="expense_income_inconsistency",
                    severity=FindingSeverity.HIGH,
                    score=0.80,
                    message="Declared expenses exceed declared income.",
                    evidence={
                        "declared_income": declared_income,
                        "declared_expenses": declared_expenses,
                    },
                    rule_id="RULE_EXPENSES_GT_INCOME",
                )

            if declared_income > 0:
                ratio = declared_expenses / declared_income

                if ratio > 2.0:
                    add_finding(
                        findings,
                        finding_type="extreme_expense_income_ratio",
                        severity=FindingSeverity.HIGH,
                        score=0.93,
                        message="Expense-to-income ratio is extremely implausible.",
                        evidence={
                            "declared_income": declared_income,
                            "declared_expenses": declared_expenses,
                            "expense_income_ratio": round(ratio, 4),
                        },
                        rule_id="RULE_EXTREME_EXPENSE_RATIO",
                    )
                elif ratio > 1.0:
                    add_finding(
                        findings,
                        finding_type="very_high_expense_income_ratio",
                        severity=FindingSeverity.HIGH,
                        score=0.82,
                        message="Expense-to-income ratio is implausibly high.",
                        evidence={
                            "declared_income": declared_income,
                            "declared_expenses": declared_expenses,
                            "expense_income_ratio": round(ratio, 4),
                        },
                        rule_id="RULE_VERY_HIGH_EXPENSE_RATIO",
                    )
                elif ratio > 0.75:
                    add_finding(
                        findings,
                        finding_type="high_expense_income_ratio",
                        severity=FindingSeverity.MEDIUM,
                        score=0.62,
                        message="Expense-to-income ratio is unusually high.",
                        evidence={
                            "declared_income": declared_income,
                            "declared_expenses": declared_expenses,
                            "expense_income_ratio": round(ratio, 4),
                        },
                        rule_id="RULE_HIGH_EXPENSE_RATIO",
                    )

        if employment_start and employment_end and employment_start > employment_end:
            add_finding(
                findings,
                finding_type="employment_inconsistency",
                severity=FindingSeverity.HIGH,
                score=0.84,
                message="Employment start date occurs after employment end date.",
                evidence={
                    "employment_start": employment_start,
                    "employment_end": employment_end,
                },
                rule_id="RULE_EMPLOYMENT_DATE_ORDER",
            )

        if declared_income is not None and declared_income > 50000000:
            add_finding(
                findings,
                finding_type="extreme_financial_implausibility",
                severity=FindingSeverity.HIGH,
                score=0.88,
                message="Declared income is implausibly high for a normal tax declaration.",
                evidence={"declared_income": declared_income},
                rule_id="RULE_EXTREME_INCOME_IMPLAUSIBILITY",
            )

        if declared_expenses is not None and declared_expenses > 100000000:
            add_finding(
                findings,
                finding_type="extreme_financial_implausibility",
                severity=FindingSeverity.HIGH,
                score=0.90,
                message="Declared expenses are implausibly high for a normal tax declaration.",
                evidence={"declared_expenses": declared_expenses},
                rule_id="RULE_EXTREME_EXPENSE_IMPLAUSIBILITY",
            )

        if (
            declared_income is not None
            and declared_expenses is not None
            and declared_income >= 10000000
            and declared_expenses >= 50000000
        ):
            add_finding(
                findings,
                finding_type="severe_income_expense_mismatch",
                severity=FindingSeverity.HIGH,
                score=0.91,
                message="Income and expenses jointly indicate a severe financial mismatch.",
                evidence={
                    "declared_income": declared_income,
                    "declared_expenses": declared_expenses,
                },
                rule_id="RULE_SEVERE_FINANCIAL_MISMATCH",
            )

    if not findings:
        rule_score = 0.05
    else:
        rule_score = round(min(1.0, max(f.score for f in findings)), 4)

    return {
        "rule_score": rule_score,
        "findings": [f.model_dump(mode="json") for f in findings],
    }
