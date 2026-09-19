from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(relative: str):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


def _serialized(*payloads) -> str:
    return "\n".join(str(payload).lower() for payload in payloads)


def test_stg_and_prod_compose_are_local_only_and_isolated() -> None:
    for env, compose_name, prefix in (
        ("staging", "compose.observability.stg.yml", "stg"),
        ("production", "compose.observability.prod.yml", "prod"),
    ):
        compose = load_yaml(compose_name)
        services = compose["services"]
        assert {"api", "collector", "prometheus", "alertmanager", "grafana"} <= set(services)
        assert compose["networks"]["observability"]["internal"] is True
        for name in ("api", "collector", "prometheus", "alertmanager", "grafana"):
            for port in services[name].get("ports", []):
                assert port.startswith("127.0.0.1:"), f"{compose_name}:{name} exposes {port}"
        assert services["api"]["environment"]["APP_ENV"] == env
        assert services["collector"]["environment"]["APP_ENV"] == env
        assert services["collector"]["read_only"] is True
        assert "ALL" in services["collector"]["cap_drop"]
        assert services["collector"]["security_opt"] == ["no-new-privileges:true"]
        assert f"collector-queue-{prefix}" in compose["volumes"]
        assert f"prometheus-data-{prefix}" in compose["volumes"]
        assert f"grafana-data-{prefix}" in compose["volumes"]


def test_stg_and_prod_prometheus_use_environment_labels_and_alertmanager() -> None:
    expected = {
        "stg": "staging",
        "prod": "production",
    }
    for folder, env in expected.items():
        config = load_yaml(f"observability/{folder}/prometheus.yml")
        jobs = {job["job_name"]: job for job in config["scrape_configs"]}
        assert "/etc/prometheus/rules/alerts.yaml" in config["rule_files"]
        assert config["alerting"]["alertmanagers"][0]["static_configs"][0]["targets"] == ["alertmanager:9093"]
        assert jobs["environment-observability-api"]["static_configs"][0]["targets"] == ["api:8000"]
        assert jobs["environment-observability-api"]["static_configs"][0]["labels"]["environment"] == env
        assert jobs["environment-observability-collector"]["static_configs"][0]["targets"] == ["collector:8888"]
        assert jobs["environment-observability-collector"]["static_configs"][0]["labels"]["environment"] == env


def test_stg_and_prod_do_not_commit_secrets_or_fake_notification_success() -> None:
    stg_compose = load_yaml("compose.observability.stg.yml")
    prod_compose = load_yaml("compose.observability.prod.yml")
    stg_alertmanager = load_yaml("observability/stg/alertmanager.yml")
    prod_alertmanager = load_yaml("observability/prod/alertmanager.yml")
    serialized = _serialized(stg_compose, prod_compose, stg_alertmanager, prod_alertmanager)

    for forbidden in (
        "bearer ",
        "webhook_url",
        "api_key",
        "password:",
        "token:",
        "teams.webhook",
        "hooks.office.com",
    ):
        assert forbidden not in serialized

    assert stg_alertmanager["route"]["receiver"] == "stg-notification-pending"
    assert prod_alertmanager["route"]["receiver"] == "prod-notification-pending"
    assert stg_alertmanager["receivers"] == [{"name": "stg-notification-pending"}]
    assert prod_alertmanager["receivers"] == [{"name": "prod-notification-pending"}]


def test_retention_is_stricter_by_environment() -> None:
    stg = load_yaml("compose.observability.stg.yml")
    prod = load_yaml("compose.observability.prod.yml")
    assert "--storage.tsdb.retention.time=14d" in stg["services"]["prometheus"]["command"]
    assert "--storage.tsdb.retention.time=30d" in prod["services"]["prometheus"]["command"]
