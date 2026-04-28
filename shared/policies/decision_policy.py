from __future__ import annotations

from typing import List

from shared.models.decision import (
    DecisionResult,
    DefenseAction,
    DefenseHandoff,
)
from shared.models.risk import RiskAssessment


HOSTILE_KEYWORDS_MINEFIELD = {
    "bot",
    "credential",
    "credential_stuffing",
    "scam",
    "fraud",
    "payload",
    "resource_exhaustion",
    "lateral_movement",
    "automated_abuse",
    "weaponized",
    "hostile",
    "malicious",
    "extreme_financial_implausibility",
    "extreme_expense_income_ratio",
    "severe_income_expense_mismatch",
}

PROBING_KEYWORDS_HONEYPOT = {
    "recon",
    "reconnaissance",
    "probing",
    "enumeration",
    "scanner",
    "automated_probe",
    "suspicious_behavior_pattern",
}

SOCIAL_ENGINEERING_KEYWORDS_DECEIVE = {
    "impersonation",
    "identity_mismatch",
    "social_engineering",
    "semantic_manipulation",
    "forged_context",
    "employment_inconsistency",
    "deceptive_payload",
    "deceptive",
}


def _normalize_strings(values: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip().lower()
        if text:
            out.append(text)
    return out


def _collect_indicators(risk: RiskAssessment) -> List[str]:
    findings: List[str] = []

    for item in risk.findings or []:
        try:
            code = getattr(item, "code", None)
            description = getattr(item, "description", None)
            finding_type = getattr(item, "finding_type", None)
            message = getattr(item, "message", None)

            if code:
                findings.append(str(code))
            if description:
                findings.append(str(description))
            if finding_type:
                findings.append(str(finding_type))
            if message:
                findings.append(str(message))
        except Exception:
            findings.append(str(item))

    semantic = _normalize_strings(
        [
            risk.semantic_reasoning or "",
            getattr(risk, "semantic_assessment", "") or "",
        ]
    )
    recommended = _normalize_strings([risk.recommended_action or ""])
    return _normalize_strings(findings) + semantic + recommended


def _contains_any(indicators: List[str], keywords: set[str]) -> bool:
    for item in indicators:
        for keyword in keywords:
            if keyword in item:
                return True
    return False


def _contains_many(indicators: List[str], keywords: set[str], minimum: int) -> bool:
    matches = 0
    seen = set()
    for item in indicators:
        for keyword in keywords:
            if keyword in item and keyword not in seen:
                seen.add(keyword)
                matches += 1
    return matches >= minimum


def _has_indicator(indicators: List[str], keyword: str) -> bool:
    return any(keyword in item for item in indicators)


def build_decision_result(risk: RiskAssessment) -> DecisionResult:
    total_score = float(risk.total_score or 0.0)
    confidence = float(risk.confidence or 0.0)
    indicators = _collect_indicators(risk)

    minefield_signal = _contains_any(indicators, HOSTILE_KEYWORDS_MINEFIELD)
    strong_minefield_signal = _contains_many(indicators, HOSTILE_KEYWORDS_MINEFIELD, minimum=2)
    honeypot_signal = _contains_any(indicators, PROBING_KEYWORDS_HONEYPOT)
    deceive_signal = _contains_any(indicators, SOCIAL_ENGINEERING_KEYWORDS_DECEIVE)

    hard_block = any(
        [
            _has_indicator(indicators, "invalid_income"),
            _has_indicator(indicators, "negative_expenses"),
            _has_indicator(indicators, "employment_inconsistency"),
            _has_indicator(indicators, "forged_context"),
            _has_indicator(indicators, "identity_mismatch"),
            _has_indicator(indicators, "high_expense_income_ratio"),
            _has_indicator(indicators, "very_high_expense_income_ratio"),
            _has_indicator(indicators, "extreme_expense_income_ratio"),
            _has_indicator(indicators, "severe_income_expense_mismatch"),
            _has_indicator(indicators, "extreme_financial_implausibility"),
            _has_indicator(indicators, "fraud"),
        ]
    )

    if hard_block and total_score < 0.55:
        total_score = 0.55

    if total_score >= 0.92 and minefield_signal:
        return DecisionResult(
            action=DefenseAction.MINEFIELD,
            handoff=DefenseHandoff.ESCALATE,
            policy_version="v5_master",
            confidence_label="high",
            reasons=[
                "extreme_risk_score",
                "strong_hostile_signal",
                "minefield_threshold_met",
            ],
        )

    if total_score >= 0.86 and strong_minefield_signal:
        return DecisionResult(
            action=DefenseAction.MINEFIELD,
            handoff=DefenseHandoff.ESCALATE,
            policy_version="v5_master",
            confidence_label="high",
            reasons=[
                "high_risk_score",
                "multiple_hostile_indicators_detected",
                "minefield_threshold_met",
            ],
        )

    if total_score >= 0.72 and honeypot_signal:
        return DecisionResult(
            action=DefenseAction.HONEYPOT,
            handoff=DefenseHandoff.NONE,
            policy_version="v5_master",
            confidence_label="medium",
            reasons=[
                "behavioral_probing_detected",
                "honeypot_selected",
            ],
        )

    if total_score >= 0.66 and deceive_signal:
        return DecisionResult(
            action=DefenseAction.DECEIVE,
            handoff=DefenseHandoff.NONE,
            policy_version="v5_master",
            confidence_label="medium",
            reasons=[
                "deceptive_semantic_pattern_detected",
                "deceiver_selected",
            ],
        )

    if total_score >= 0.55:
        return DecisionResult(
            action=DefenseAction.CONTAIN,
            handoff=DefenseHandoff.RETAIN,
            policy_version="v5_master",
            confidence_label="medium",
            reasons=[
                "suspicious_claim_contained",
                "hold_for_controlled_re_evaluation",
            ],
        )

    if total_score >= 0.30 or confidence < 0.50:
        return DecisionResult(
            action=DefenseAction.CONTAIN,
            handoff=DefenseHandoff.NEEDS_HUMAN_OVERSIGHT,
            policy_version="v5_master",
            confidence_label="medium",
            reasons=[
                "uncertain_case",
                "human_oversight_required",
            ],
        )

    return DecisionResult(
        action=DefenseAction.ALLOW,
        handoff=DefenseHandoff.RELEASE,
        policy_version="v5_master",
        confidence_label="low",
        reasons=[
            "low_risk_allow",
        ],
    )
