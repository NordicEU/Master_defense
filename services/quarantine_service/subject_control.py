from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict


class SubjectControlState(str, Enum):
    NORMAL = "NORMAL"
    WATCHLIST = "WATCHLIST"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"


class SubjectControlRegistry:
    def __init__(self, base_dir: Path, now_fn: Callable[[], Any]) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.now_fn = now_fn

    def _path(self, subject_id: str) -> Path:
        safe_subject_id = str(subject_id).strip()
        return self.base_dir / f"{safe_subject_id}.json"

    def load(self, subject_id: str) -> Dict[str, Any] | None:
        path = self._path(subject_id)
        if not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save(self, record: Dict[str, Any]) -> None:
        subject_id = str(record["subject_id"]).strip()
        path = self._path(subject_id)
        path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    def get_or_default(self, subject_id: str) -> Dict[str, Any]:
        subject_id = str(subject_id).strip()
        existing = self.load(subject_id)
        if existing is not None:
            return existing

        return {
            "subject_id": subject_id,
            "state": SubjectControlState.NORMAL.value,
            "reason": "",
            "linked_case_ids": [],
            "created_at": None,
            "updated_at": None,
        }

    def upsert(
        self,
        subject_id: str,
        state: SubjectControlState,
        reason: str,
        linked_case_id: str | None = None,
    ) -> Dict[str, Any]:
        subject_id = str(subject_id).strip()
        now = self.now_fn()
        existing = self.load(subject_id)

        record = existing or {
            "subject_id": subject_id,
            "state": SubjectControlState.NORMAL.value,
            "reason": "",
            "linked_case_ids": [],
            "created_at": now,
            "updated_at": now,
        }

        priority = {
            SubjectControlState.NORMAL.value: 0,
            SubjectControlState.WATCHLIST.value: 1,
            SubjectControlState.RESTRICTED.value: 2,
            SubjectControlState.BLOCKED.value: 3,
        }

        current_state = str(record.get("state", SubjectControlState.NORMAL.value))
        current_priority = priority.get(current_state, 0)
        new_priority = priority.get(state.value, 0)

        if new_priority >= current_priority:
            record["state"] = state.value
            record["reason"] = reason

        linked_case_ids = record.get("linked_case_ids", [])
        if not isinstance(linked_case_ids, list):
            linked_case_ids = []

        if linked_case_id:
            linked_case_id = str(linked_case_id).strip()
            if linked_case_id and linked_case_id not in linked_case_ids:
                linked_case_ids.append(linked_case_id)

        record["linked_case_ids"] = linked_case_ids
        record["updated_at"] = now

        if record.get("created_at") is None:
            record["created_at"] = now

        self.save(record)
        return record

    def set_state(
        self,
        subject_id: str,
        state: SubjectControlState,
        reason: str,
        linked_case_id: str | None = None,
    ) -> Dict[str, Any]:
        subject_id = str(subject_id).strip()
        now = self.now_fn()
        existing = self.load(subject_id)

        record = existing or {
            "subject_id": subject_id,
            "state": SubjectControlState.NORMAL.value,
            "reason": "",
            "linked_case_ids": [],
            "created_at": now,
            "updated_at": now,
        }

        linked_case_ids = record.get("linked_case_ids", [])
        if not isinstance(linked_case_ids, list):
            linked_case_ids = []

        if linked_case_id:
            linked_case_id = str(linked_case_id).strip()
            if linked_case_id and linked_case_id not in linked_case_ids:
                linked_case_ids.append(linked_case_id)

        record["state"] = state.value
        record["reason"] = reason
        record["linked_case_ids"] = linked_case_ids
        record["updated_at"] = now

        if record.get("created_at") is None:
            record["created_at"] = now

        self.save(record)
        return record
