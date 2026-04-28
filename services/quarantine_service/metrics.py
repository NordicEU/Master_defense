from __future__ import annotations

from collections import Counter
from typing import Dict

from shared.models.quarantine_case import QuarantineCase


def build_quarantine_metrics(cases: list[QuarantineCase]) -> Dict[str, object]:
    state_counter = Counter()
    severity_counter = Counter()
    isolation_counter = Counter()
    release_eligible = 0
    escalation_eligible = 0
    total_audit_events = 0
    total_observations = 0

    for case in cases:
        state_counter[case.current_state.value] += 1
        severity_counter[case.severity.value] += 1
        isolation_counter[case.isolation_mode.value] += 1

        if case.release_eligible:
            release_eligible += 1
        if case.escalation_eligible:
            escalation_eligible += 1

        total_audit_events += len(case.audit_trail)
        total_observations += len(case.observations)

    return {
        "total_cases": len(cases),
        "cases_by_state": dict(state_counter),
        "cases_by_severity": dict(severity_counter),
        "cases_by_isolation_mode": dict(isolation_counter),
        "release_eligible_cases": release_eligible,
        "escalation_eligible_cases": escalation_eligible,
        "total_audit_events": total_audit_events,
        "total_observations": total_observations,
    }


def render_prometheus_metrics(metrics: Dict[str, object]) -> str:
    lines: list[str] = []

    total_cases = int(metrics.get("total_cases", 0))
    release_eligible_cases = int(metrics.get("release_eligible_cases", 0))
    escalation_eligible_cases = int(metrics.get("escalation_eligible_cases", 0))
    total_audit_events = int(metrics.get("total_audit_events", 0))
    total_observations = int(metrics.get("total_observations", 0))

    lines.append("# HELP quarantine_cases_total Total number of quarantine cases.")
    lines.append("# TYPE quarantine_cases_total gauge")
    lines.append(f"quarantine_cases_total {total_cases}")

    lines.append("# HELP quarantine_release_eligible_cases Total number of release-eligible quarantine cases.")
    lines.append("# TYPE quarantine_release_eligible_cases gauge")
    lines.append(f"quarantine_release_eligible_cases {release_eligible_cases}")

    lines.append("# HELP quarantine_escalation_eligible_cases Total number of escalation-eligible quarantine cases.")
    lines.append("# TYPE quarantine_escalation_eligible_cases gauge")
    lines.append(f"quarantine_escalation_eligible_cases {escalation_eligible_cases}")

    lines.append("# HELP quarantine_audit_events_total Total number of audit events across quarantine cases.")
    lines.append("# TYPE quarantine_audit_events_total gauge")
    lines.append(f"quarantine_audit_events_total {total_audit_events}")

    lines.append("# HELP quarantine_observations_total Total number of observations across quarantine cases.")
    lines.append("# TYPE quarantine_observations_total gauge")
    lines.append(f"quarantine_observations_total {total_observations}")

    for state, count in sorted((metrics.get("cases_by_state") or {}).items()):
        lines.append("# HELP quarantine_cases_by_state Number of quarantine cases by state.")
        lines.append("# TYPE quarantine_cases_by_state gauge")
        lines.append(f'quarantine_cases_by_state{{state="{state}"}} {count}')

    for severity, count in sorted((metrics.get("cases_by_severity") or {}).items()):
        lines.append("# HELP quarantine_cases_by_severity Number of quarantine cases by severity.")
        lines.append("# TYPE quarantine_cases_by_severity gauge")
        lines.append(f'quarantine_cases_by_severity{{severity="{severity}"}} {count}')

    for mode, count in sorted((metrics.get("cases_by_isolation_mode") or {}).items()):
        lines.append("# HELP quarantine_cases_by_isolation_mode Number of quarantine cases by isolation mode.")
        lines.append("# TYPE quarantine_cases_by_isolation_mode gauge")
        lines.append(f'quarantine_cases_by_isolation_mode{{mode="{mode}"}} {count}')

    return "\n".join(lines) + "\n"
