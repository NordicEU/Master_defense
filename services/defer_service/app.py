from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI

app = FastAPI(title="Defer Service", version="0.1.0")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "defer_service"}


@app.post("/defer")
def defer_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message": "defer placeholder received payload",
        "status": "ok",
    }
