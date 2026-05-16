from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


BASE_DIR = Path(__file__).resolve().parents[1]
GATEWAY_URL = "http://127.0.0.1:8000/route"

GREEN_INPUT = BASE_DIR / "datasets" / "green_cases" / "all_documents.jsonl"
ADVERSARIAL_INPUT = BASE_DIR / "datasets" / "adversarial_cases" / "all_documents_adversarial.jsonl"
OUTPUT_PATH = BASE_DIR / "runtime" / "results" / "replay_results.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_payload(record: dict[str, Any]) -> dict[str, Any]:
    submission_id = f"replay-{uuid4()}"
    normalized_payload = {
        "document_type": record.get("document_type"),
        "person_id": record.get("person_id"),
        "partsnummer": record.get("partsnummer"),
        "inntektsaar": record.get("inntektsaar"),
        "fields": record.get("fields", {}),
        "raw_payload_keys": sorted(list(record.keys())),
    }

    return {
        "submission": {
            "submission_id": submission_id,
            "source": "dataset_replay",
            "payload_type": "tax_document",
            "source_label": record.get("label"),
            "document_type": record.get("document_type"),
            "person_id": record.get("person_id"),
        },
        "normalized_payload": normalized_payload,
    }


def replay_records(client: httpx.Client, records: list[dict[str, Any]], label: str, limit: int = 20) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for idx, record in enumerate(records[:limit], start=1):
        payload = build_payload(record)
        started = time.perf_counter()

        try:
            response = client.post(GATEWAY_URL, json=payload)
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            response.raise_for_status()
            data = response.json()
            risk_assessment = data.get("risk_assessment", {})
            downstream_response = data.get("downstream_response", {})
            downstream_response = downstream_response if isinstance(downstream_response, dict) else {}

            results.append({
                "dataset_label": label,
                "record_index": idx,
                "document_type": record.get("document_type"),
                "person_id": record.get("person_id"),
                "source_label": record.get("label"),
                "flow_result": data.get("flow_result"),
                "submission_id": data.get("submission_id"),
                "decision_action": data.get("action"),
                "decision_handoff": data.get("handoff"),
                "risk_score": risk_assessment.get("total_score"),
                "decision_confidence": risk_assessment.get("confidence"),
                "semantic_reasoning": risk_assessment.get("semantic_reasoning"),
                "downstream_id": (
                    downstream_response.get("case_id")
                    or downstream_response.get("defer_id")
                    or downstream_response.get("review_id")
                    or downstream_response.get("deception_id")
                    or downstream_response.get("submission_id")
                ),
                "latency_ms": latency_ms,
            })
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            results.append({
                "dataset_label": label,
                "record_index": idx,
                "document_type": record.get("document_type"),
                "person_id": record.get("person_id"),
                "source_label": record.get("label"),
                "flow_result": "ERROR",
                "error": str(exc),
                "latency_ms": latency_ms,
            })

    return results


def main() -> None:
    green_records = load_jsonl(GREEN_INPUT)
    adversarial_records = load_jsonl(ADVERSARIAL_INPUT)

    print(f"Loaded green records: {len(green_records)}")
    print(f"Loaded adversarial records: {len(adversarial_records)}")

    all_results: list[dict[str, Any]] = []

    with httpx.Client(timeout=120.0) as client:
        all_results.extend(replay_records(client, green_records, "green"))
        all_results.extend(replay_records(client, adversarial_records, "adversarial"))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for item in all_results:
            f.write(json.dumps(item) + "\n")

    print(f"Replay results written to: {OUTPUT_PATH}")
    print(f"Total replayed records: {len(all_results)}")


if __name__ == "__main__":
    main()
