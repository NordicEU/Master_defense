from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = BASE_DIR / "runtime" / "results" / "replay_results.jsonl"
DEFAULT_OUTPUT = BASE_DIR / "runtime" / "results" / "replay_summary.md"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Replay results not found: {path}\n"
            "Run `python3 scripts/replay_cases.py` first, or pass a file with `--input`."
        )

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = (len(ordered) - 1) * percent
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def route_label(record: dict[str, Any]) -> str:
    value = record.get("flow_result") or record.get("decision_action") or "UNKNOWN"
    return str(value).upper()


def dataset_label(record: dict[str, Any]) -> str:
    return str(record.get("dataset_label") or "unlabelled").lower()


def expected_miss_rate(label: str, route_counts: Counter[str], total: int) -> tuple[str, float]:
    if total <= 0:
        return ("n/a", 0.0)

    allowed = route_counts.get("ALLOW", 0)
    errors = route_counts.get("ERROR", 0)

    if label == "green":
        return ("false_positive_rate", round((total - allowed - errors) / total, 4))
    if label == "adversarial":
        return ("false_negative_rate", round(allowed / total, 4))
    return ("non_allow_rate", round((total - allowed - errors) / total, 4))


def summarize(records: list[dict[str, Any]]) -> str:
    by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_dataset[dataset_label(record)].append(record)

    lines: list[str] = []
    lines.append("# Replay Evaluation Summary")
    lines.append("")
    lines.append(f"Total records: {len(records)}")
    lines.append("")

    lines.append("## Route Distribution")
    lines.append("")
    lines.append("| Dataset | Requests | ALLOW | CONTAIN | DECEIVE | HONEYPOT | MINEFIELD | ERROR | Other | Main rate |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    known_routes = {"ALLOW", "CONTAIN", "DECEIVE", "HONEYPOT", "MINEFIELD", "ERROR"}
    for label in sorted(by_dataset):
        items = by_dataset[label]
        routes = Counter(route_label(item) for item in items)
        other = sum(count for route, count in routes.items() if route not in known_routes)
        rate_name, rate = expected_miss_rate(label, routes, len(items))
        lines.append(
            "| "
            f"{label} | {len(items)} | {routes.get('ALLOW', 0)} | {routes.get('CONTAIN', 0)} | "
            f"{routes.get('DECEIVE', 0)} | {routes.get('HONEYPOT', 0)} | {routes.get('MINEFIELD', 0)} | "
            f"{routes.get('ERROR', 0)} | {other} | {rate_name}: {rate:.2%} |"
        )

    lines.append("")
    lines.append("## Latency")
    lines.append("")
    lines.append("| Dataset | Mean ms | Median ms | P95 ms | Min ms | Max ms |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")

    for label in sorted(by_dataset):
        latencies = [
            float(item["latency_ms"])
            for item in by_dataset[label]
            if isinstance(item.get("latency_ms"), int | float)
        ]
        if not latencies:
            lines.append(f"| {label} | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |")
            continue

        lines.append(
            f"| {label} | {mean(latencies):.2f} | {median(latencies):.2f} | "
            f"{percentile(latencies, 0.95):.2f} | {min(latencies):.2f} | {max(latencies):.2f} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- For green data, the main rate estimates the share not routed to `ALLOW`.")
    lines.append("- For adversarial data, the main rate estimates the share routed to `ALLOW`.")
    lines.append("- Review `ERROR` rows separately before interpreting the rates.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize replay evaluation results.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    records = load_jsonl(args.input)
    summary = summarize(records)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary, encoding="utf-8")
    print(f"Wrote replay summary to {args.output}")


if __name__ == "__main__":
    main()
