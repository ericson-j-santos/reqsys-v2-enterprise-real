from __future__ import annotations

from scripts.pending_development_orchestrator import classify_risk, looks_like_ci_failure


def item(title: str, body: str = "") -> dict:
    return {
        "number": 1,
        "title": title,
        "body": body,
        "labels": [],
        "assignees": [],
    }


def test_sensitive_hint_does_not_match_inside_innocent_word() -> None:
    risk, reason = classify_risk(item("Plano desenhado com segurança"))

    assert risk == "standard"
    assert reason == "no_sensitive_hint"


def test_sensitive_hint_still_matches_literal_password_term() -> None:
    risk, reason = classify_risk(item("Rotacionar senha da conta de homologação"))

    assert risk == "high"
    assert reason == "sensitive_hint:senha"


def test_sensitive_hint_matches_underscore_delimited_token() -> None:
    risk, reason = classify_risk(item("Atualizar token_name do executor"))

    assert risk == "high"
    assert reason == "sensitive_hint:token"


def test_sensitive_multiword_hint_is_preserved() -> None:
    risk, reason = classify_risk(item("Revisar acesso ao Key Vault"))

    assert risk == "high"
    assert reason == "sensitive_hint:key vault"


def test_ci_hint_does_not_match_inside_ordinary_word() -> None:
    assert looks_like_ci_failure(item("Falha na credencial do executor")) is False
    assert looks_like_ci_failure(item("Checklist com erro de negócio")) is False


def test_ci_failure_literal_terms_are_still_detected() -> None:
    assert looks_like_ci_failure(item("Falha no CI: validação obrigatória")) is True
    assert looks_like_ci_failure(item("Workflow com erro no backend")) is True
    assert looks_like_ci_failure(item("Pipeline-error no gate rápido")) is True
