from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.pc24x7-token-broker.yml"
RENDER_BLUEPRINT = ROOT / "render.token-broker.yaml"
SERVICE_NAME = "agent-token-broker"
STATE_DIR = "/var/lib/reqsys-token-broker"
STATE_DB = f"{STATE_DIR}/token-broker.db"
SECRET_NAME = "broker_token_state_encryption_key"


def _compose() -> dict:
    payload = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _service() -> dict:
    service = _compose()["services"][SERVICE_NAME]
    assert isinstance(service, dict)
    return service


def test_pc24x7_compose_is_primary_persistent_single_host_runtime() -> None:
    service = _service()

    assert service["build"] == {
        "context": ".",
        "dockerfile": "backend/token_broker/Dockerfile",
    }
    assert service["restart"] == "unless-stopped"
    assert service["ports"] == ["127.0.0.1:${BROKER_HOST_PORT:-18080}:8080"]
    assert service["volumes"] == [f"reqsys-token-broker-state:{STATE_DIR}"]
    assert "deploy" not in service
    assert "reqsys-token-broker-state" in _compose()["volumes"]


def test_pc24x7_compose_requires_stable_https_url_and_external_secret_file() -> None:
    service = _service()
    env = service["environment"]

    assert env["BROKER_PUBLIC_BASE_URL"] == (
        "${BROKER_PUBLIC_BASE_URL:?configure a stable HTTPS endpoint}"
    )
    assert env["BROKER_TOKEN_STATE_DB_PATH"] == STATE_DB
    assert env["BROKER_BOOTSTRAP_ENABLED"] == "${BROKER_BOOTSTRAP_ENABLED:-true}"
    assert service["secrets"] == [SECRET_NAME]
    assert _compose()["secrets"][SECRET_NAME]["file"] == (
        "${BROKER_TOKEN_STATE_ENCRYPTION_KEY_FILE:?configure the host secret file path}"
    )


def test_pc24x7_compose_injects_secret_without_committing_its_value() -> None:
    service = _service()
    command = "\n".join(service["command"])
    raw = COMPOSE.read_text(encoding="utf-8")

    assert "/run/secrets/broker_token_state_encryption_key" in command
    assert "BROKER_TOKEN_STATE_ENCRYPTION_KEY=\"$$(cat" in command
    assert "BROKER_GITHUB_APP_CLIENT_SECRET" not in raw
    assert "BROKER_GITHUB_APP_REFRESH_TOKEN_BOOTSTRAP" not in raw
    assert "COPILOT_AGENT_TOKEN=" not in raw


def test_render_blueprint_is_not_part_of_primary_runtime_anymore() -> None:
    assert not RENDER_BLUEPRINT.exists()
