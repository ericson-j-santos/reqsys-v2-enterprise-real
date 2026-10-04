from app.core import cofre_verificador_cego as modulo
from app.core.cofre_verificador_cego import VerificadorCegoIndisponivel, verificar_valor_cego


def test_verificador_cego_true_false_sem_expor_marcador(monkeypatch):
    monkeypatch.setattr(modulo, 'obter_chave_operacional', lambda: 'p' * 48)

    assert verificar_valor_cego('K', 'valor', 'valor').match is True
    assert verificar_valor_cego('K', 'valor', 'outro').match is False
    assert verificar_valor_cego('K', 'valor', 'valor').value_exposed is False


def test_pepper_fraco_falha_fechado(monkeypatch):
    monkeypatch.setattr(modulo, 'read_secret_from_vault', lambda _key: 'curto')

    try:
        modulo.obter_chave_operacional()
    except VerificadorCegoIndisponivel:
        pass
    else:
        raise AssertionError('pepper fraco deve falhar fechado')
