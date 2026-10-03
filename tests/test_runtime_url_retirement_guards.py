from __future__ import annotations

import re
from urllib.parse import urlsplit

import pytest

from scripts import (
    cofre_human_token,
    register_lifecycle_evidence,
    relatorio_qualidade_ia_pendentes,
    validar_frontend_auth_redirect,
    validar_login_azure_operacional,
)
from tools.geradores.gerar_servico_notificador_repositorio import (
    gerar,
)
from tools.geradores.gerar_servico_notificador_repositorio import (
    testar as run_generated_tests,
)


def test_cofre_requires_explicit_provider_neutral_https_urls() -> None:
    with pytest.raises(cofre_human_token.CofreTokenError, match="explícita"):
        cofre_human_token._base_url("dev", None)
    with pytest.raises(cofre_human_token.CofreTokenError, match="retirado definitivamente"):
        cofre_human_token._base_url("dev", "https://legacy.fly.dev")
    with pytest.raises(cofre_human_token.CofreTokenError, match="HTTPS"):
        cofre_human_token._frontend_origin("dev", "http://app.example.net")

    assert (
        cofre_human_token._base_url("dev", "https://api-dev.example.net/")
        == "https://api-dev.example.net"
    )
    assert (
        cofre_human_token._frontend_origin("dev", "https://app-dev.example.net/")
        == "https://app-dev.example.net"
    )


def test_frontend_validator_rejects_fly_before_fetch(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        validar_frontend_auth_redirect,
        "_fetch",
        lambda url, *_args, **_kwargs: calls.append(url),
    )

    with pytest.raises(ValueError, match="retirado definitivamente"):
        validar_frontend_auth_redirect.validate_public_frontend(
            "https://legacy.fly.dev"
        )

    assert calls == []


def test_login_validator_rejects_fly_before_fetch(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        validar_login_azure_operacional,
        "_get_json",
        lambda url, *_args, **_kwargs: calls.append(url),
    )

    with pytest.raises(
        validar_login_azure_operacional.ValidationError,
        match="retirado definitivamente",
    ):
        validar_login_azure_operacional.validar_config(
            "https://legacy.fly.dev",
            "https://app.example.net/auth/callback.html",
        )

    assert calls == []


def test_lifecycle_rejects_fly_before_post(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        register_lifecycle_evidence,
        "_post_json",
        lambda *args, **kwargs: calls.append(str(args or kwargs)),
    )

    with pytest.raises(ValueError, match="retirado definitivamente"):
        register_lifecycle_evidence.register(
            base_url="https://legacy.fly.dev",
            token="not-logged",
            requirement_code="REQ-1",
            evidence_type="pr",
            repo="owner/repo",
            reference="1",
            evidence_url=None,
            title=None,
            environment=None,
            provider="github",
            correlation_id="test",
            attempts=1,
        )

    assert calls == []


def test_quality_report_rejects_fly_before_get(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        relatorio_qualidade_ia_pendentes,
        "_get_json",
        lambda url, *_args, **_kwargs: calls.append(url),
    )

    with pytest.raises(ValueError, match="retirado definitivamente"):
        relatorio_qualidade_ia_pendentes.analisar_ambiente(
            "prod",
            "https://legacy.fly.dev",
        )

    assert calls == []


def test_generated_notifier_requires_explicit_authorized_gateway(tmp_path) -> None:
    gerar(tmp_path, force=False)
    run_generated_tests(tmp_path)

    service = (
        tmp_path / "teams-repo-notifier-service" / "src" / "service.py"
    ).read_text(encoding="utf-8")
    readme = (
        tmp_path / "teams-repo-notifier-service" / "README.md"
    ).read_text(encoding="utf-8")
    assert "DEFAULT_BASE_URL" not in service
    assert "TEAMS_GATEWAY_BASE_URL" in service
    documented_urls = {
        urlsplit(value.rstrip("`.,)"))
        for value in re.findall(r"https://[^\s]+", readme)
    }
    assert urlsplit("https://gateway.example.net") in documented_urls
