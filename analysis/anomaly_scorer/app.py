from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from shared.models.findings import AnalysisFinding, FindingSeverity

app = FastAPI(title="Anomaly Scorer", version="4.0.0")

BASE_DIR = Path(__file__).resolve().parents[2]
BASELINE_PATH = BASE_DIR / "datasets" / "reference" / "baseline_summary.json"


class StatisticalRequest(BaseModel):
    normalized_payload: Dict[str, Any] = Field(default_factory=dict)


def load_baseline() -> Dict[str, Any]:
    if not BASELINE_PATH.exists():
        return {}
    with BASELINE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


BASELINE = load_baseline()


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
            source_component="anomaly_scorer",
            severity=severity,
            score=score,
            message=message,
            evidence=evidence,
            rule_id=rule_id,
        )
    )


def normalize_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "anomaly_scorer"}


@app.post("/score")
def score_anomaly(request: StatisticalRequest) -> Dict[str, Any]:
    payload = request.normalized_payload
    findings: List[AnalysisFinding] = []

    declared_income = _safe_float(payload.get("declared_income"))
    declared_expenses = _safe_float(payload.get("declared_expenses"))

    if declared_income is not None:
        if declared_income > 50000000:
            add_finding(
                findings,
                "income_outlier",
                FindingSeverity.HIGH,
                0.92,
                "Declared income is extremely far above expected baseline.",
                {"declared_income": declared_income},
                "STAT_EXTREME_INCOME_OUTLIER",
            )
        elif declared_income > 5000000:
            add_finding(
                findings,
                "income_outlier",
                FindingSeverity.HIGH,
                0.78,
                "Declared income is significantly above expected baseline.",
                {"declared_income": declared_income},
                "STAT_HIGH_INCOME_OUTLIER",
            )
        elif declared_income > 900000:
            add_finding(
                findings,
                "income_outlier",
                FindingSeverity.MEDIUM,
                0.58,
                "Declared income is moderately above expected baseline.",
                {"declared_income": declared_income},
                "STAT_MODERATE_INCOME_OUTLIER",
            )

    if (
        declared_income is not None
        and declared_expenses is not None
        and declared_income > 0
    ):
        ratio = declared_expenses / declared_income

        if ratio > 2.0:
            add_finding(
                findings,
                "expense_ratio_outlier",
                FindingSeverity.HIGH,
                0.93,
                "Expense-to-income ratio is extremely implausible.",
                {
                    "declared_income": declared_income,
                    "declared_expenses": declared_expenses,
                    "expense_income_ratio": round(ratio, 4),
                },
                "STAT_EXPENSE_RATIO_EXTREME",
            )
        elif ratio > 1.0:
            add_finding(
                findings,
                "expense_ratio_outlier",
                FindingSeverity.HIGH,
                0.78,
                "Expense-to-income ratio is implausibly high.",
                {
                    "declared_income": declared_income,
                    "declared_expenses": declared_expenses,
                    "expense_income_ratio": round(ratio, 4),
                },
                "STAT_EXPENSE_RATIO_HIGH",
            )
        elif ratio > 0.75:
            add_finding(
                findings,
                "expense_ratio_outlier",
                FindingSeverity.MEDIUM,
                0.62,
                "Expense-to-income ratio is unusually high.",
                {
                    "declared_income": declared_income,
                    "declared_expenses": declared_expenses,
                    "expense_income_ratio": round(ratio, 4),
                },
                "STAT_EXPENSE_RATIO_ELEVATED",
            )
        elif ratio > 0.45:
            add_finding(
                findings,
                "expense_ratio_outlier",
                FindingSeverity.MEDIUM,
                0.55,
                "Expense-to-income ratio is higher than expected baseline.",
                {
                    "declared_income": declared_income,
                    "declared_expenses": declared_expenses,
                    "expense_income_ratio": round(ratio, 4),
                },
                "STAT_EXPENSE_RATIO_MODERATE",
            )

    if declared_expenses is not None:
        if declared_expenses > 100000000:
            add_finding(
                findings,
                "expense_outlier",
                FindingSeverity.HIGH,
                0.94,
                "Declared expenses are extremely above expected baseline.",
                {"declared_expenses": declared_expenses},
                "STAT_EXTREME_EXPENSES",
            )
        elif declared_expenses > 5000000:
            add_finding(
                findings,
                "expense_outlier",
                FindingSeverity.HIGH,
                0.76,
                "Declared expenses are significantly above expected baseline.",
                {"declared_expenses": declared_expenses},
                "STAT_HIGH_EXPENSES",
            )
        elif declared_expenses > 300000:
            add_finding(
                findings,
                "expense_outlier",
                FindingSeverity.MEDIUM,
                0.57,
                "Declared expenses are above expected baseline.",
                {"declared_expenses": declared_expenses},
                "STAT_MODERATE_EXPENSES",
            )

    document_type = payload.get("document_type")
    fields = payload.get("fields", {})

    field_presence = BASELINE.get("field_presence_by_document_type", {})
    document_type_counts = BASELINE.get("document_type_counts", {})
    categorical_counts = BASELINE.get("categorical_value_counts_by_document_type", {})

    if document_type:
        if document_type not in document_type_counts:
            add_finding(
                findings,
                "unknown_document_type",
                FindingSeverity.HIGH,
                0.72,
                "Document type not observed in green baseline.",
                {"document_type": document_type},
                "BASELINE_UNKNOWN_DOCUMENT_TYPE",
            )
        else:
            expected_fields = set(field_presence.get(document_type, {}).keys())
            provided_fields = set(fields.keys()) if isinstance(fields, dict) else set()

            if expected_fields:
                missing_fields = sorted(list(expected_fields - provided_fields))
                unexpected_fields = sorted(list(provided_fields - expected_fields))

                missing_ratio = len(missing_fields) / max(len(expected_fields), 1)
                unexpected_ratio = len(unexpected_fields) / max(len(expected_fields), 1)

                if missing_ratio >= 0.60:
                    add_finding(
                        findings,
                        "missing_expected_fields",
                        FindingSeverity.HIGH,
                        0.74,
                        "Submission is missing a large share of fields expected for this document type.",
                        {
                            "document_type": document_type,
                            "missing_fields": missing_fields,
                            "missing_ratio": round(missing_ratio, 4),
                        },
                        "BASELINE_MISSING_EXPECTED_FIELDS_HIGH",
                    )
                elif missing_ratio >= 0.25:
                    add_finding(
                        findings,
                        "missing_expected_fields",
                        FindingSeverity.MEDIUM,
                        0.44,
                        "Submission is missing some fields expected for this document type.",
                        {
                            "document_type": document_type,
                            "missing_fields": missing_fields,
                            "missing_ratio": round(missing_ratio, 4),
                        },
                        "BASELINE_MISSING_EXPECTED_FIELDS_MEDIUM",
                    )

                if unexpected_ratio >= 0.60:
                    add_finding(
                        findings,
                        "unexpected_fields",
                        FindingSeverity.HIGH,
                        0.70,
                        "Submission contains many unexpected fields for this document type.",
                        {
                            "document_type": document_type,
                            "unexpected_fields": unexpected_fields,
                            "unexpected_ratio": round(unexpected_ratio, 4),
                        },
                        "BASELINE_UNEXPECTED_FIELDS_HIGH",
                    )
                elif unexpected_ratio >= 0.25:
                    add_finding(
                        findings,
                        "unexpected_fields",
                        FindingSeverity.MEDIUM,
                        0.40,
                        "Submission contains some unexpected fields for this document type.",
                        {
                            "document_type": document_type,
                            "unexpected_fields": unexpected_fields,
                            "unexpected_ratio": round(unexpected_ratio, 4),
                        },
                        "BASELINE_UNEXPECTED_FIELDS_MEDIUM",
                    )

            known_value_map = categorical_counts.get(document_type, {})
            if isinstance(fields, dict):
                for field_name, field_value in fields.items():
                    value_counter = known_value_map.get(field_name, {})
                    if not value_counter:
                        continue

                    normalized = normalize_value(field_value)
                    total_known = sum(value_counter.values())
                    seen_count = value_counter.get(normalized, 0)

                    if seen_count == 0:
                        add_finding(
                            findings,
                            "unknown_field_value",
                            FindingSeverity.MEDIUM,
                            0.38,
                            "Field value not observed in green baseline.",
                            {
                                "document_type": document_type,
                                "field_name": field_name,
                                "field_value": normalized,
                            },
                            "BASELINE_UNKNOWN_FIELD_VALUE",
                        )
                    else:
                        frequency = seen_count / max(total_known, 1)
                        if frequency < 0.005:
                            add_finding(
                                findings,
                                "rare_field_value",
                                FindingSeverity.MEDIUM,
                                0.34,
                                "Field value is extremely rare in green baseline.",
                                {
                                    "document_type": document_type,
                                    "field_name": field_name,
                                    "field_value": normalized,
                                    "frequency": round(frequency, 4),
                                },
                                "BASELINE_RARE_FIELD_VALUE_EXTREME",
                            )
                        elif frequency < 0.01:
                            add_finding(
                                findings,
                                "rare_field_value",
                                FindingSeverity.MEDIUM,
                                0.28,
                                "Field value is very rare in green baseline.",
                                {
                                    "document_type": document_type,
                                    "field_name": field_name,
                                    "field_value": normalized,
                                    "frequency": round(frequency, 4),
                                },
                                "BASELINE_RARE_FIELD_VALUE",
                            )

    if not findings:
        statistical_score = 0.08
    else:
        statistical_score = round(min(1.0, max(f.score for f in findings)), 4)

    return {
        "statistical_score": statistical_score,
        "findings": [f.model_dump(mode="json") for f in findings],
    }
