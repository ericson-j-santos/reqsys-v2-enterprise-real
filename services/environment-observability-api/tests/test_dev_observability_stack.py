from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(relative: str):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


def test_dev_stack_is_local_only_and_environment_isolated() -> None:
    compose = load_yaml("compose.observability.dev.yml")
    services = compose["services"]
    assert {"api", "collector", "prometheus", "alertmanager", "grafana"} <= set(services)
    assert compose["networks"]["observability"]["internal"] is True
    for name in ("api", "collector", "prometheus", "alertmanager", "grafana"):
        for port in services[name].get("ports", []):
            assert port.startswith("127.0.0.1:")
    assert services["api"]["environment"]["APP_ENV"] == "development"
    assert services["collector"]["environment"]["APP_ENV"] == "development"


def test_prometheus_scrapes_api_collector_and_loads_alerts() -> None:
    config = load_yaml("observability/dev/prometheus.yml")
    jobs = {job["job_name"]: job for job in config["scrape_configs"]}
    assert jobs["environment-observability-api"]["static_configs"][0]["targets"] == ["api:8000"]
    assert jobs["otel-collector"]["static_configs"][0]["targets"] == ["collector:8888"]
    assert "/etc/prometheus/rules/alerts.yaml" in config["rule_files"]
    assert config["alerting"]["alertmanagers"][0]["static_configs"][0]["targets"] == ["alertmanager:9093"]


def test_grafana_and_alertmanager_are_provisioned_without_secrets() -> None:
    datasource = load_yaml("observability/dev/grafana-provisioning/datasources/prometheus.yml")
    dashboard = load_yaml("observability/dev/grafana-provisioning/dashboards/dashboard.yml")
    alertmanager = load_yaml("observability/dev/alertmanager.yml")
    assert datasource["datasources"][0]["url"] == "http://prometheus:9090"
    assert dashboard["providers"][0]["folder"] == "DEV"
    assert alertmanager["route"]["receiver"] == "dev-log"
    serialized = str({"datasource": datasource, "dashboard": dashboard, "alertmanager": alertmanager}).lower()
    for forbidden in ("bearer ", "password:", "token:", "webhook_url"):
        assert forbidden not in serialized
