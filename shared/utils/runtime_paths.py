from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

DEFAULT_RUNTIME_DIR = BASE_DIR / "runtime"
DEFAULT_QUARANTINE_DIR = DEFAULT_RUNTIME_DIR / "quarantine_cases"
DEFAULT_AUDIT_DIR = DEFAULT_RUNTIME_DIR / "audit_logs"

QUARANTINE_RUNTIME_DIR = Path(
    os.getenv("QUARANTINE_RUNTIME_DIR", str(DEFAULT_QUARANTINE_DIR))
)

AUDIT_LOG_DIR = Path(
    os.getenv("AUDIT_LOG_DIR", str(DEFAULT_AUDIT_DIR))
)

QUARANTINE_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
