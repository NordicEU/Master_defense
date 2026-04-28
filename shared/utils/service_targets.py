from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


MINEFIELD_URL = _env("MINEFIELD_URL", "http://127.0.0.1:8006/defer")
DECEIVE_URL = _env("DECEIVE_URL", "http://127.0.0.1:8007/deception")
HONEYPOT_URL = _env("HONEYPOT_URL", "http://127.0.0.1:8005/review")

TRANSFER_TARGET_URLS = {
    "MINEFIELD": MINEFIELD_URL,
    "DECEIVE": DECEIVE_URL,
    "HONEYPOT": HONEYPOT_URL,
}
