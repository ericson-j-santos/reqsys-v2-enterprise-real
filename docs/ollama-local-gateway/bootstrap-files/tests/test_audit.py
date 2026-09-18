from reqsys_ollama_gateway.audit import auditar, mascarar


def test_mascarar_remove_credencial() -> None:
    texto = 'minha senha: secreta e api_key=abc'
    mascarado = mascarar(texto)
    assert 'secreta' not in mascarado or '[REDACTED]' in mascarado


def test_auditar_nao_propaga_pii(caplog) -> None:
    with caplog.at_level('INFO'):
        auditar('teste', {'correlation_id': 'c1', 'prompt': 'senha: xyz', 'response': 'ok'})
    assert 'c1' in caplog.text
    assert 'xyz' not in caplog.text
