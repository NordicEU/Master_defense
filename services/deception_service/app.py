from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="Deception Service", version="0.1.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "deception_service"}


@app.post("/deception")
def deception_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message": "deception placeholder received payload",
        "status": "ok",
    }
