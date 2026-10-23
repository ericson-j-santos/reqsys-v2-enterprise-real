from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

from scripts.validate_local_stack_contract import (
    ContractError,
    evaluate_contract,
    interpolate,
    validate_production_contract,
)


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


def _production_contract(overrides: dict[str, str] | None = None) -> dict:
    # Synthetic inputs only: never inherit host environment, .env or secrets.
    environment = dict(PRODUCTION_REQUIRED_ENV)
    environment["GATEWAY_PORT"] = "18081"
    environment.update(overrides or {})
    model = evaluate_contract(
        (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
        (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"),
        environment,
    )
    validate_production_contract(model, environment)
    return model


def test_restart_policy_is_fail_fast_except_in_production() -> None:
    base_services = _yaml("docker-compose.yml")["services"]
    model = _production_contract()
    prod_services = model["services"]
    active_services = set(model["active_services"])

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
    model = _production_contract()
    services = model["services"]

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
    assert "mailhog" not in model["active_services"]
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
    with pytest.raises(ContractError, match=required_name):
        _production_contract({required_name: ""})


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

    output = " ".join(
        ANSI_ESCAPE.sub("", result.stdout + result.stderr).replace("|", " ").split()
    )
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


# Native projection controls run in this existing explicit Fast CI test target.
# They are contract tests, not captured Docker output or container/runtime proof.
@pytest.mark.parametrize(
    ("value", "environment", "expected"),
    [
        ("${OUTER:-http://localhost:${PORT:-8081}}", {}, "http://localhost:8081"),
        ("${OUTER:-http://localhost:${PORT:-8081}}", {"PORT": "18081"}, "http://localhost:18081"),
        ("${VALUE:-fallback}", {"VALUE": ""}, "fallback"),
        ("${VALUE-fallback}", {"VALUE": ""}, ""),
        ("$VALUE/${ABSENT}", {"VALUE": "set"}, "set/"),
        ("$${POSTGRES_USER:-reqsys_app}", {"POSTGRES_USER": "ignored"}, "${POSTGRES_USER:-reqsys_app}"),
        ("$$VALUE", {"VALUE": "ignored"}, "$VALUE"),
        ("${VALUE:?required}", {"VALUE": "explicit"}, "explicit"),
    ],
)
def test_native_interpolation_contract(value, environment, expected) -> None:
    assert interpolate(value, environment) == expected


@pytest.mark.parametrize("required_name", sorted(PRODUCTION_REQUIRED_ENV))
def test_native_contract_rejects_unset_required_values(required_name: str) -> None:
    environment = dict(PRODUCTION_REQUIRED_ENV)
    del environment[required_name]
    with pytest.raises(ContractError, match=required_name):
        evaluate_contract(
            (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
            (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"),
            environment,
        )


def test_native_projection_uses_explicit_inputs_and_preserves_dollar_literal(monkeypatch) -> None:
    def forbidden_process(*args, **kwargs):
        raise AssertionError("native contract must not invoke a process")

    monkeypatch.setattr(subprocess, "run", forbidden_process)
    monkeypatch.setenv("POSTGRES_PASSWORD", "untrusted-host-synthetic")
    monkeypatch.setenv("COMPOSE_PROFILES", "local-mail")
    model = _production_contract()
    assert model["scope"] == "reqsys-production-contract-v1"
    assert model["active_services"] == ["api", "db", "frontend", "kb", "nginx"]
    expected_url = (
        "postgresql+psycopg2://reqsys_app:"
        + PRODUCTION_REQUIRED_ENV["POSTGRES_PASSWORD"] + "@db:5432/reqsys"
    )
    assert model["services"]["api"]["environment"]["DATABASE_URL"] == expected_url
    assert model["services"]["api"]["depends_on"] == {"db": {"condition": "service_healthy"}}
    assert model["services"]["db"]["healthcheck"]["test"] == [
        "CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-reqsys_app} -d ${POSTGRES_DB:-reqsys}"
    ]
    assert model["services"]["nginx"]["ports"] == [
        {"target": 80, "published": "18081", "protocol": "tcp"}
    ]


def test_native_interpolates_each_file_before_merge() -> None:
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    original = "JWT_ISSUER=${JWT_ISSUER:-reqsys-api}"
    assert original in base
    base = base.replace(original, "JWT_ISSUER=${BASE_ONLY_REQUIRED:?must not be hidden}", 1)
    with pytest.raises(ContractError, match="BASE_ONLY_REQUIRED"):
        evaluate_contract(
            base, (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"),
            dict(PRODUCTION_REQUIRED_ENV),
        )


def test_native_replaces_healthcheck_test_and_merges_environment_maps() -> None:
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    base = base.replace(
        "  frontend:\n",
        '  frontend:\n    healthcheck:\n      test: ["CMD", "echo", "base-only"]\n',
        1,
    )
    environment = {**PRODUCTION_REQUIRED_ENV, "GATEWAY_PORT": "18081"}
    model = evaluate_contract(base, (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"), environment)
    validate_production_contract(model, environment)
    assert "base-only" not in model["services"]["frontend"]["healthcheck"]["test"]
    assert model["services"]["api"]["environment"]["ALLOW_DEMO_LOGIN"] == "false"
    assert model["services"]["api"]["environment"]["GEMINI_API_KEY"] == ""


def test_native_profile_activation_is_explicit_not_a_production_acceptance() -> None:
    model = evaluate_contract(
        (ROOT / "docker-compose.yml").read_text(encoding="utf-8"),
        (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"),
        dict(PRODUCTION_REQUIRED_ENV),
        profiles=("local-mail",),
    )
    assert "mailhog" in model["active_services"]
    with pytest.raises(ContractError, match="production_service_set_invalid"):
        validate_production_contract(model, dict(PRODUCTION_REQUIRED_ENV))


@pytest.mark.parametrize(
    ("target", "old", "new", "expected_error"),
    [
        ("base", 'restart: "no"', 'restart: "always"', "base_restart_not_fail_fast"),
        ("prod", 'restart: "on-failure:5"', 'restart: "always"', "production_restart_not_bounded"),
        ("prod", 'ALLOW_DEMO_LOGIN: "false"', 'ALLOW_DEMO_LOGIN: "true"', "production_identity_or_demo_invalid"),
        ("prod", "depends_on: !override", "depends_on:", "active_dependency_has_disabled_profile"),
        ("prod", "profiles: [local-mail]", "profiles: [unexpected]", "mailhog_must_be_opt_in"),
        ("base", "  nginx:\n", '  nginx:\n    ports: ["18082:80"]\n', "gateway_publication_invalid"),
        ("base", "  db:\n", '  db:\n    ports: ["15432:5432"]\n', "private_service_published"),
        ("prod", "http://127.0.0.1/healthz", "http://127.0.0.1/unready", "frontend_healthcheck_invalid"),
        ("prod", "http://127.0.0.1/api/health", "http://127.0.0.1/api/unready", "gateway_healthcheck_invalid"),
        ("prod", "frontend:\n        condition: service_healthy",
         "frontend:\n        condition: service_started", "gateway_frontend_dependency_invalid"),
        ("prod", "  api:\n", "  api:\n    deploy:\n      restart_policy:\n        condition: any\n", "unsupported_service_field"),
        ("prod", "services:\n", "include: other.yml\nservices:\n", "unsupported_top_level_field"),
        ("prod", "  api:\n", "  api:\n    env_file: .env\n", "unsupported_service_field"),
        ("prod", "  api:\n", "  api:\n    extends: {service: other}\n", "unsupported_service_field"),
        ("prod", "    environment:\n", "    environment: !override\n", "override_outside_depends_on"),
        ("prod", "${GATEWAY_PORT:-8081}:80", "18081-18082:80", "unsupported_port_syntax"),
        ("prod", '    restart: "on-failure:5"', '    restart: "no"\n    restart: "on-failure:5"', "unsupported_or_duplicate_mapping_key"),
        ("prod", "depends_on: !override", "depends_on: !reset", "unsupported_or_invalid_yaml"),
        ("base", "JWT_SECRET=${JWT_SECRET:-trocar-em-producao}", "JWT_SECRET", "environment_entry_requires_explicit_value"),
        ("prod", "    healthcheck:\n", "    healthcheck:\n      disable: true\n", "unsupported_healthcheck_field"),
    ],
)
def test_native_contract_rejects_invariant_and_unsupported_mutations(target, old, new, expected_error) -> None:
    base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    prod = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    source = base if target == "base" else prod
    assert old in source, "mutation must apply to the current versioned input"
    mutated = source.replace(old, new, 1)
    environment = {**PRODUCTION_REQUIRED_ENV, "GATEWAY_PORT": "18081"}
    with pytest.raises(ContractError, match=expected_error):
        model = evaluate_contract(mutated if target == "base" else base,
                                  mutated if target == "prod" else prod, environment)
        validate_production_contract(model, environment)
