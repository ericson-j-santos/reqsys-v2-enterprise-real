from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "render.token-broker.yaml"
SERVICE_NAME = "reqsys-agent-token-broker"
STATE_DIR = "/var/lib/reqsys-token-broker"
STATE_DB = f"{STATE_DIR}/token-broker.db"


def _service() -> dict:
    payload = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    services = payload.get("services") if isinstance(payload, dict) else None
    assert isinstance(services, list) and len(services) == 1
    service = services[0]
    assert isinstance(service, dict)
    return service


def _env_map(service: dict) -> dict[str, dict]:
    entries = service.get("envVars")
    assert isinstance(entries, list)
    return {entry["key"]: entry for entry in entries}


def test_blueprint_uses_single_paid_instance_with_persistent_state() -> None:
    service = _service()

    assert service["type"] == "web"
    assert service["name"] == SERVICE_NAME
    assert service["runtime"] == "docker"
    assert service["plan"] == "0.5c-512mb"
    assert service["branch"] == "main"
    assert service["dockerfilePath"] == "./backend/token_broker/Dockerfile"
    assert service["dockerContext"] == "."
    assert service["autoDeployTrigger"] == "off"
    assert service["healthCheckPath"] == "/healthz"
    assert service["numInstances"] == 1

    disk = service["disk"]
    assert disk["mountPath"] == STATE_DIR
    assert disk["sizeGB"] == 1


def test_blueprint_generates_encryption_key_and_never_commits_secret_values() -> None:
    env = _env_map(_service())

    encryption_key = env["BROKER_TOKEN_STATE_ENCRYPTION_KEY"]
    assert encryption_key == {
        "key": "BROKER_TOKEN_STATE_ENCRYPTION_KEY",
        "generateValue": True,
    }

    assert env["BROKER_TOKEN_STATE_DB_PATH"]["value"] == STATE_DB
    assert "BROKER_GITHUB_APP_CLIENT_SECRET" not in env
    assert "BROKER_GITHUB_APP_REFRESH_TOKEN_BOOTSTRAP" not in env
    assert "COPILOT_AGENT_TOKEN" not in env


def test_blueprint_self_wires_public_url_and_bootstrap_contract() -> None:
    env = _env_map(_service())

    assert env["BROKER_PUBLIC_BASE_URL"]["fromService"] == {
        "type": "web",
        "name": SERVICE_NAME,
        "envVarKey": "RENDER_EXTERNAL_URL",
    }
    assert env["BROKER_BOOTSTRAP_ENABLED"]["value"] == "true"
    assert env["BROKER_AUDIENCE"]["value"] == "reqsys-copilot-agent-token-broker"
    assert env["BROKER_ALLOWED_REPOSITORY"]["value"] == (
        "ericson-j-santos/reqsys-v2-enterprise-real"
    )
    assert env["BROKER_ALLOWED_WORKFLOW_REF"]["value"] == (
        "ericson-j-santos/reqsys-v2-enterprise-real/.github/workflows/"
        "pending-development-orchestrator.yml@refs/heads/main"
    )
    assert env["BROKER_ALLOWED_REF"]["value"] == "refs/heads/main"
    assert env["BROKER_ALLOWED_EVENTS"]["value"] == "workflow_dispatch,schedule"
