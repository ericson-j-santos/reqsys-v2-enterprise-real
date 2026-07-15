from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_grafana_dashboard_has_required_operational_panels() -> None:
    dashboard = json.loads((ROOT / "observability/grafana-dashboard.json").read_text())
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert {
        "Taxa de requisições",
        "Taxa de erros",
        "Latência p95",
        "Falhas de exportação OTEL",
        "Spans recusados",
        "Ocupação da fila OTEL",
    } <= titles
    serialized = json.dumps(dashboard).lower()
    for forbidden in ("authorization", "cookie", "password", "cpf", "email"):
        assert forbidden not in serialized


def test_prometheus_rules_cover_red_and_collector_loss() -> None:
    rules = yaml.safe_load((ROOT / "observability/prometheus-alerts.yaml").read_text())
    alerts = {
        rule["alert"]
        for group in rules["groups"]
        for rule in group["rules"]
    }
    assert {
        "EnvironmentObservabilityApiHighErrorRate",
        "EnvironmentObservabilityApiHighLatencyP95",
        "OtelCollectorExporterFailures",
        "OtelCollectorReceiverRefusedSpans",
        "OtelCollectorQueueNearCapacity",
        "OtelCollectorDown",
    } <= alerts


def test_alert_rules_define_duration_and_severity() -> None:
    rules = yaml.safe_load((ROOT / "observability/prometheus-alerts.yaml").read_text())
    for group in rules["groups"]:
        for rule in group["rules"]:
            assert rule.get("for")
            assert rule["labels"]["severity"] in {"info", "warning", "critical"}
            assert rule["annotations"]["summary"]
            assert rule["annotations"]["description"]
