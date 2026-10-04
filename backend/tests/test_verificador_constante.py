from app.core.verificador_constante import comparar_constante


def test_comparar_constante():
    assert comparar_constante('mesmo', 'mesmo') is True
    assert comparar_constante('mesmo', 'diferente') is False
