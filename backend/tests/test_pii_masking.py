"""Testes do mascaramento de PII compartilhado (ADR-002)."""

from app.core.pii_masking import (
    mascarar_cpf,
    mascarar_email,
    mascarar_pii,
    mascarar_token,
)


def test_mascarar_email_preserva_dominio_e_inicial():
    assert mascarar_email("usuario@empresa.com") == "u***@empresa.com"


def test_mascarar_email_invalido_retorna_dado_mascarado():
    assert mascarar_email("nao-e-email") == "[DADO_MASCARADO]"
    assert mascarar_email(None) == "[DADO_MASCARADO]"
    assert mascarar_email("") == "[DADO_MASCARADO]"


def test_mascarar_cpf_formata_parcial():
    assert mascarar_cpf("123.456.789-01") == "***.456.789-**"
    assert mascarar_cpf("12345678901") == "***.456.789-**"


def test_mascarar_cpf_invalido_retorna_dado_mascarado():
    assert mascarar_cpf("123") == "[DADO_MASCARADO]"
    assert mascarar_cpf(None) == "[DADO_MASCARADO]"


def test_mascarar_token_sempre_redige_por_completo():
    assert mascarar_token("qualquer-token-secreto") == "[SEGREDO_REMOVIDO]"
    assert mascarar_token(None) == "[SEGREDO_REMOVIDO]"


def test_mascarar_pii_remove_cpf_e_email_em_texto_livre():
    texto = "Contato: joao@empresa.com, CPF 123.456.789-01"
    mascarado = mascarar_pii(texto)

    assert "joao@empresa.com" not in mascarado
    assert "123.456.789-01" not in mascarado
    assert mascarado.count("[DADO_MASCARADO]") == 2
