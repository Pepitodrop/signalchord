#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "infrastructure/monitoring/prometheus-rules/signalchord-alerts.yml"
DASHBOARD = ROOT / "infrastructure/monitoring/grafana/provisioning/dashboards/signalchord-overview.json"
OBSERVABILITY_DOC = ROOT / "docs/observability.md"


def validate_rules() -> list[str]:
    text = RULES.read_text(encoding="utf-8")
    failures: list[str] = []
    alerts = re.split(r"\n\s*-\s+alert:\s+", "\n" + text)[1:]
    if len(alerts) < 5:
        failures.append("expected at least five production alert rules")
    for alert in alerts:
        name = alert.splitlines()[0].strip()
        for fragment in ["expr:", "for:", "severity:", "owner:", "slo:", "summary:", "runbook_url: docs/runbooks/"]:
            if fragment not in alert:
                failures.append(f"alert {name} is missing {fragment}")
    return failures


def validate_dashboard() -> list[str]:
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    failures: list[str] = []
    if dashboard.get("uid") != "signalchord-production-overview":
        failures.append("dashboard uid must be stable")
    panels = dashboard.get("panels", [])
    if len(panels) < 6:
        failures.append("dashboard must contain the core API, freshness, lag, delivery, telemetry and error panels")
    for panel in panels:
        if not panel.get("title"):
            failures.append(f"dashboard panel {panel.get('id')} is missing a title")
        targets = panel.get("targets") or []
        if not targets or not all(target.get("expr") for target in targets):
            failures.append(f"dashboard panel {panel.get('title')} is missing Prometheus expressions")
    return failures


def validate_docs() -> list[str]:
    text = OBSERVABILITY_DOC.read_text(encoding="utf-8")
    required = [
        "Article-to-alert freshness",
        "Control-plane API availability",
        "Realtime delivery",
        "Telemetry retention",
        "External evidence still required",
    ]
    return [f"observability doc missing {value!r}" for value in required if value not in text]


def main() -> int:
    failures = validate_rules() + validate_dashboard() + validate_docs()
    if failures:
        print("observability validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("observability validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
