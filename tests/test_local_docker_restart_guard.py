from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
ANSI_ESCAPE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
PRODUCTION_REQUIRED_ENV = {
    "JWT_SECRET": "production-contract-secret-at-least-32-characters",
    "JWT_ISSUER": "reqsys-production",
    "JWT_AUDIENCE": "reqsys-frontend",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_CLIENT_ID": "00000000-0000-0000-0000-000000000002",
    "CORS_ORIGINS": "https://app.example.test",
    "POSTGRES_PASSWORD": "production-contract-database-password",
}


def _yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8")) or {}


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _bash() -> str | None:
    bash = shutil.which("bash")
    if not bash:
        return None
    probe = subprocess.run(
        [bash, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    return bash if probe.returncode == 0 else None


def _production_compose_config(
    overrides: dict[str, str] | None = None,
    *,
    config_args: tuple[str, ...] = ("--format", "json"),
) -> subprocess.CompletedProcess[str]:
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose indisponivel")

    environment = os.environ.copy()
    environment.update(PRODUCTION_REQUIRED_ENV)
    environment["GATEWAY_PORT"] = "18081"
    if overrides:
        environment.update(overrides)

    return subprocess.run(
        [
            docker,
            "compose",
            "--project-directory",
            str(ROOT),
            "--project-name",
            "reqsys-prod-contract",
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(ROOT / "docker-compose.prod.yml"),
            "config",
            *config_args,
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_restart_policy_is_fail_fast_except_in_production() -> None:
    base_services = _yaml("docker-compose.yml")["services"]
    result = _production_compose_config()
    assert result.returncode == 0, result.stderr
    prod_services = json.loads(result.stdout)["services"]
    active_result = _production_compose_config(config_args=("--services",))
    assert active_result.returncode == 0, active_result.stderr
    active_services = set(active_result.stdout.splitlines())

    assert all(service.get("restart") == "no" for service in base_services.values())
    assert active_services == set(base_services) - {"mailhog"}
    assert all(
        prod_services[name].get("restart") == "on-failure:5"
        for name in active_services
    )
    if "mailhog" in prod_services:
        assert "local-mail" in prod_services["mailhog"].get("profiles", [])
        assert prod_services["mailhog"].get("restart") == "no"


def test_production_effective_contract_is_secure_and_reachable() -> None:
    result = _production_compose_config()
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]

    api = services["api"]
    environment = api["environment"]
    assert environment["APP_ENV"] == "production"
    assert environment["PUBLIC_ENVIRONMENT"] == "production"
    assert environment["ALLOW_DEMO_LOGIN"] == "false"
    for name, value in PRODUCTION_REQUIRED_ENV.items():
        if name != "POSTGRES_PASSWORD":
            assert environment[name] == value
    assert environment["MOVIMENTO_EMAIL_SMTP_HOST"] == ""
    assert "mailhog" not in api["depends_on"]
    active_result = _production_compose_config(config_args=("--services",))
    assert active_result.returncode == 0, active_result.stderr
    assert "mailhog" not in active_result.stdout.splitlines()
    if "mailhog" in services:
        assert "local-mail" in services["mailhog"].get("profiles", [])

    database = services["db"]
    assert database["environment"]["POSTGRES_PASSWORD"] == PRODUCTION_REQUIRED_ENV["POSTGRES_PASSWORD"]

    frontend = services["frontend"]
    assert frontend["build"]["dockerfile"] == "Dockerfile.prod"
    assert frontend["build"]["args"]["VITE_API_URL"] == "/api"
    assert "healthz" in " ".join(frontend["healthcheck"]["test"])

    gateway = services["nginx"]
    assert any(
        port["target"] == 80 and port["published"] == "18081"
        for port in gateway["ports"]
    )
    assert gateway["depends_on"]["frontend"]["condition"] == "service_healthy"
    gateway_healthcheck = " ".join(gateway["healthcheck"]["test"])
    assert "http://127.0.0.1/" in gateway_healthcheck
    assert "/api/health" in gateway_healthcheck


@pytest.mark.parametrize("required_name", sorted(PRODUCTION_REQUIRED_ENV))
def test_production_compose_fails_fast_when_required_value_is_missing(
    required_name: str,
) -> None:
    result = _production_compose_config({required_name: ""})

    assert result.returncode != 0
    assert required_name in result.stderr


def test_frontend_production_target_serves_static_spa_and_preserves_dev_default() -> None:
    development_dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    production_dockerfile = (ROOT / "frontend" / "Dockerfile.prod").read_text(
        encoding="utf-8"
    )
    nginx_config = (ROOT / "frontend" / "nginx.static.conf").read_text(encoding="utf-8")

    assert "RUN npm ci" in production_dockerfile
    assert "FROM nginx:alpine" in production_dockerfile
    assert "COPY --from=build /app/dist /usr/share/nginx/html" in production_dockerfile
    assert development_dockerfile.rstrip().endswith('CMD ["npm", "run", "dev"]')
    assert "try_files $uri $uri/ /index.html;" in nginx_config
    assert "location = /healthz" in nginx_config


@pytest.mark.parametrize(
    ("invalid_name", "invalid_value", "expected_message"),
    [
        ("JWT_SECRET", "curto", "JWT_SECRET"),
        ("CORS_ORIGINS", "https://app.example.test, *", "CORS_ORIGINS"),
        ("AZURE_CLIENT_ID", "not-a-uuid", "AZURE_CLIENT_ID"),
    ],
)
def test_publish_preflight_rejects_invalid_production_values_before_docker(
    tmp_path: Path,
    invalid_name: str,
    invalid_value: str,
    expected_message: str,
) -> None:
    bash = _bash()
    if not bash:
        pytest.skip("Bash indisponivel")

    marker = tmp_path / "docker-was-called"
    docker_sentinel = tmp_path / "docker-sentinel"
    docker_sentinel.write_text(
        "#!/usr/bin/env bash\n"
        ': > "$DOCKER_SENTINEL_MARKER"\n'
        "exit 99\n",
        encoding="utf-8",
    )
    docker_sentinel.chmod(0o755)

    environment = os.environ.copy()
    environment.update(PRODUCTION_REQUIRED_ENV)
    environment[invalid_name] = invalid_value
    environment["DOCKER_BIN"] = str(docker_sentinel)
    environment["DOCKER_SENTINEL_MARKER"] = str(marker)

    result = subprocess.run(
        [bash, str(ROOT / "scripts" / "publicar_ambiente.sh"), "prod"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert expected_message in output
    assert "Nenhum container foi iniciado" in output
    assert not marker.exists(), "o preflight invalido chegou a invocar Docker"


def test_publish_runs_the_application_production_gate_before_starting() -> None:
    script = (ROOT / "scripts" / "publicar_ambiente.sh").read_text(
        encoding="utf-8"
    )

    assert "settings.validate_production_gates()" in script
    assert "run --build --rm --no-deps -T api" in script
    assert script.count("validate_application_production_gate compose") == 2

    gate_calls = [
        index
        for index in range(len(script))
        if script.startswith("    validate_application_production_gate compose", index)
    ]
    production_starts = [
        index
        for index in range(len(script))
        if script.startswith('    "${compose[@]}" up --build', index)
    ]
    assert len(gate_calls) == 2
    assert len(production_starts) == 3  # dev, hml e prod
    assert gate_calls[0] < production_starts[1]
    assert gate_calls[1] < production_starts[2]


@pytest.mark.parametrize("overlay", ["docker-compose.dev.yml", "docker-compose.test.yml"])
def test_non_production_overlays_do_not_reenable_restart(overlay: str) -> None:
    services = _yaml(overlay)["services"]
    assert all("restart" not in service for service in services.values())


def test_windows_bootstrap_uses_preflight_and_explicit_dev_overlay() -> None:
    script = (ROOT / "scripts" / "subir-stack-sem-colisao.ps1").read_text(
        encoding="utf-8"
    )

    assert "testar-preflight-docker.ps1" in script
    assert "docker-compose.dev.yml" in script
    assert "'--project-name', 'reqsys-dev'" in script
    assert "config --quiet" in script
    assert "--wait --wait-timeout 120" in script
    assert "docker compose up -d" not in script


def test_scheduler_is_opt_in_and_does_not_request_elevation() -> None:
    script = (ROOT / "scripts" / "agendar-subida-stack-docker.ps1").read_text(
        encoding="utf-8"
    )

    assert "[switch]$HabilitarAgendamento" in script
    assert "if (-not $HabilitarAgendamento)" in script
    assert "[string]$TriggerType = 'AtLogon'" in script
    assert "/RL LIMITED" in script
    assert "/RL HIGHEST" not in script
    assert script.index("if ($Desagendar)") < script.index("Resolve-Path")


@pytest.mark.parametrize(
    "script_name",
    [
        "configurar-ssrs.ps1",
        "reiniciar-docker-seguro.ps1",
        "reiniciar-stack-limpo.ps1",
    ],
)
def test_windows_entrypoints_do_not_start_base_compose_alone(
    script_name: str,
) -> None:
    script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

    assert "testar-preflight-docker.ps1" in script
    assert "docker-compose.dev.yml" in script
    assert "config --quiet" in script
    assert "docker compose up" not in script


def test_cross_platform_publish_script_uses_explicit_overlays() -> None:
    script = (ROOT / "scripts" / "publicar_ambiente.sh").read_text(
        encoding="utf-8"
    )

    assert "preflight dev" in script
    assert "preflight prod" in script
    assert "docker-compose.dev.yml" in script
    assert "docker-compose.prod.yml" in script
    assert "config --quiet" in script
    assert "docker compose up" not in script


def test_fast_ci_runs_restart_guard_for_runtime_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci-fast-operational.yml").read_text(
        encoding="utf-8"
    )

    assert '"docker-compose*.yml"' in workflow
    assert '"frontend/Dockerfile*"' in workflow
    assert "tests/test_local_docker_restart_guard.py" in workflow
    assert "pytest pyyaml" in workflow


def test_preflight_blocks_missing_frontend_manifest_before_docker() -> None:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell indisponivel")

    with tempfile.TemporaryDirectory(prefix="reqsys-docker-preflight-") as temp_dir:
        project_dir = Path(temp_dir)
        required = [
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "backend/Dockerfile",
            "frontend/Dockerfile",
            "infra/nginx/default.dev.conf",
        ]
        for relative_path in required:
            path = project_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-File",
                str(ROOT / "scripts" / "testar-preflight-docker.ps1"),
                "-ProjetoDir",
                str(project_dir),
                "-Ambiente",
                "dev",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    output = " ".join(ANSI_ESCAPE.sub("", result.stdout + result.stderr).split())
    assert result.returncode != 0
    assert "frontend" in output
    assert "package.json" in output
    assert "Nenhum comando Docker" in output
    assert "foi executado" in output


def test_scheduler_refuses_creation_without_explicit_opt_in() -> None:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell indisponivel")

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-File",
            str(ROOT / "scripts" / "agendar-subida-stack-docker.ps1"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "HabilitarAgendamento" in output
