from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="Review Service", version="0.1.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "review_service"}


@app.post("/review")
def review_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message": "review placeholder received payload",
        "status": "ok",
    }
