from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[2]
ROUTING_DIR = BASE_DIR / "runtime" / "routing_tokens"
ROUTING_DIR.mkdir(parents=True, exist_ok=True)


def create_routing_token(data: Dict[str, Any]) -> str:
    token = str(uuid4())
    token_path = ROUTING_DIR / f"{token}.json"
    with token_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return token


def get_routing_token_data(token: str) -> Optional[Dict[str, Any]]:
    token_path = ROUTING_DIR / f"{token}.json"
    if not token_path.exists():
        return None
    with token_path.open("r", encoding="utf-8") as f:
        return json.load(f)
