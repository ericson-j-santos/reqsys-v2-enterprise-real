from __future__ import annotations

from app.core.verificador_constante import comparar_constante


def test_comparar_constante_retorna_true_para_valores_iguais():
    assert comparar_constante('valor', 'valor') is True


def test_comparar_constante_retorna_false_para_valores_diferentes():
    assert comparar_constante('valor', 'outro') is False
