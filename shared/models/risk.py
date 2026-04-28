from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisFinding(BaseModel):
    code: str
    description: Optional[str] = None
    weight: Optional[float] = None


class RiskAssessment(BaseModel):
    assessment_id: str
    rule_score: float = Field(default=0.0)
    statistical_score: float = Field(default=0.0)
    context_score: float = Field(default=0.0)
    semantic_score: float = Field(default=0.0)
    total_score: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    findings: List[AnalysisFinding] = Field(default_factory=list)
    semantic_reasoning: str = Field(default="")
    recommended_action: str = Field(default="CONTAIN")
    assessed_at: Any = Field(default_factory=utc_now)

    @field_validator(
        "rule_score",
        "statistical_score",
        "context_score",
        "semantic_score",
        "total_score",
        "confidence",
        mode="before",
    )
    @classmethod
    def _coerce_float(cls, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    @field_validator("findings", mode="before")
    @classmethod
    def _normalize_findings(cls, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []

        if not isinstance(value, list):
            value = [value]

        normalized: list[dict[str, Any]] = []

        for item in value:
            if item is None:
                continue

            if isinstance(item, str):
                text = item.strip()
                if text:
                    normalized.append(
                        {
                            "code": text,
                            "description": text,
                            "weight": None,
                        }
                    )
                continue

            if isinstance(item, dict):
                code = str(item.get("code") or item.get("description") or item.get("name") or "").strip()
                if not code:
                    continue
                normalized.append(
                    {
                        "code": code,
                        "description": item.get("description") or code,
                        "weight": item.get("weight"),
                    }
                )
                continue

            try:
                code = str(getattr(item, "code", "") or getattr(item, "description", "") or str(item)).strip()
                if code:
                    normalized.append(
                        {
                            "code": code,
                            "description": getattr(item, "description", None) or code,
                            "weight": getattr(item, "weight", None),
                        }
                    )
            except Exception:
                continue

        return normalized

    @field_validator("recommended_action", mode="before")
    @classmethod
    def _normalize_action(cls, value: Any) -> str:
        text = str(value or "CONTAIN").strip().upper()
        if text in {"ALLOW", "CONTAIN", "DECEIVE", "HONEYPOT", "MINEFIELD"}:
            return text
        if text in {"REVIEW", "QUARANTINE"}:
            return "CONTAIN"
        return "CONTAIN"
