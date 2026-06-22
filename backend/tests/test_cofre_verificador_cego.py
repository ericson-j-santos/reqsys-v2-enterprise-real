from __future__ import annotations

import pytest

from app.core import cofre_verificador_cego as modulo
from app.core.cofre_verificador_cego import VerificadorCegoIndisponivel, verificar_valor_cego

VALOR_OPERACIONAL = 'valor-operacional-com-no-minimo-32-caracteres'


def test_verificador_cego_retorna_true_quando_valor_igual(monkeypatch):
    monkeypatch.setattr(modulo, 'read_secret_from_vault', lambda key: VALOR_OPERACIONAL)

    result = verificar_valor_cego('API_KEY', 'valor-real', 'valor-real')

    assert result.match is True
    assert result.value_exposed is False
    assert result.verifier_version == 'cego-v1'


def test_verificador_cego_retorna_false_quando_valor_diferente(monkeypatch):
    monkeypatch.setattr(modulo, 'read_secret_from_vault', lambda key: VALOR_OPERACIONAL)

    result = verificar_valor_cego('API_KEY', 'valor-real', 'valor-errado')

    assert result.match is False


def test_verificador_cego_exige_valor_operacional_forte(monkeypatch):
    monkeypatch.setattr(modulo, 'read_secret_from_vault', lambda key: 'fraco')

    with pytest.raises(VerificadorCegoIndisponivel):
        verificar_valor_cego('API_KEY', 'valor-real', 'valor-real')


def test_verificador_cego_nao_expoe_marcador_ou_valor(monkeypatch):
    monkeypatch.setattr(modulo, 'read_secret_from_vault', lambda key: VALOR_OPERACIONAL)

    result = verificar_valor_cego('API_KEY', 'valor-real', 'valor-real')

    assert not hasattr(result, 'digest')
    assert not hasattr(result, 'fingerprint')
    assert not hasattr(result, 'valor_armazenado')
    assert not hasattr(result, 'valor_candidato')
