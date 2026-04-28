from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
REFERENCE_DIR = BASE_DIR / "datasets" / "reference"
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def normalize_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"Skipping invalid JSON on line {line_number}: {exc}")
    return records


def main() -> None:
    input_path = BASE_DIR / "datasets" / "green_cases" / "all_documents_expanded.jsonl"
    output_path = REFERENCE_DIR / "baseline_summary.json"

    if not input_path.exists():
        raise FileNotFoundError(f"Could not find input file: {input_path}")

    records = load_jsonl(input_path)
    if not records:
        raise ValueError("No records found in input JSONL file.")

    document_type_counter: Counter[str] = Counter()
    field_presence_by_doc_type: dict[str, Counter[str]] = defaultdict(Counter)
    numeric_values_by_field: dict[str, list[float]] = defaultdict(list)
    categorical_value_counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))

    for record in records:
        document_type = record.get("document_type", "UNKNOWN")
        document_type_counter[document_type] += 1

        fields = record.get("fields", {})
        if not isinstance(fields, dict):
            continue

        for field_name, field_value in fields.items():
            field_presence_by_doc_type[document_type][field_name] += 1

            if is_number(field_value):
                numeric_values_by_field[field_name].append(float(field_value))
            else:
                normalized = normalize_value(field_value)
                categorical_value_counts[document_type][field_name][normalized] += 1

    numeric_field_stats: dict[str, dict[str, float]] = {}
    for field_name, values in numeric_values_by_field.items():
        if not values:
            continue
        numeric_field_stats[field_name] = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": round(mean(values), 4),
        }

    field_presence_summary: dict[str, dict[str, int]] = {}
    for document_type, counter in field_presence_by_doc_type.items():
        field_presence_summary[document_type] = dict(counter.most_common())

    categorical_value_summary: dict[str, dict[str, dict[str, int]]] = {}
    for document_type, fields_map in categorical_value_counts.items():
        categorical_value_summary[document_type] = {}
        for field_name, counter in fields_map.items():
            categorical_value_summary[document_type][field_name] = dict(counter.most_common())

    baseline = {
        "total_records": len(records),
        "document_type_counts": dict(document_type_counter),
        "field_presence_by_document_type": field_presence_summary,
        "numeric_field_stats": numeric_field_stats,
        "categorical_value_counts_by_document_type": categorical_value_summary,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)

    print(f"Baseline written to: {output_path}")
    print(f"Total records: {len(records)}")
    print("Document types:")
    for doc_type, count in document_type_counter.most_common():
        print(f"  - {doc_type}: {count}")


if __name__ == "__main__":
    main()
