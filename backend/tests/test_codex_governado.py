from app.db import Base, engine, SessionLocal
from app.services import codex_governado as svc
from app.services.codex_governado import analisar_governado, resumo_operacional, validar_conteudo_seguro


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_bloqueia_conteudo_sensivel():
    achados = validar_conteudo_seguro(['minha senha: exemplo'])
    assert achados


def test_analise_mock_gera_payload_reqsys():
    resultado = analisar_governado(
        provider='mock',
        contexto='validar endpoint governado',
        entrada='codigo sem dado sensivel',
        usuario={'sub': 'tester@example.com'},
        correlation_id='codex-test-001',
        publicar_no_reqsys=False,
    )

    assert resultado['bloqueado'] is False
    assert resultado['correlation_id'] == 'codex-test-001'
    assert resultado['provider'] == 'mock'
    assert resultado['reqsys_payload']['origem'] == 'codex-governado'
    assert resultado['reqsys_publicacao']['publicado'] is False
    assert resultado['score_confianca'] >= 70


def test_provider_ollama_gateway_usa_api_governada(monkeypatch):
    chamadas = {}

    def fake_post_json(url, payload, headers=None, timeout=45):
        chamadas['url'] = url
        chamadas['payload'] = payload
        chamadas['headers'] = headers or {}
        chamadas['timeout'] = timeout
        return {'response': 'resposta via gateway local'}

    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_url', 'http://gateway.local:8008')
    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_api_key', 'test-key')
    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_model', 'qwen2.5-coder:7b')
    monkeypatch.setattr(svc.settings, 'codex_ollama_gateway_timeout_seconds', 30)
    monkeypatch.setattr(svc, '_post_json', fake_post_json)

    resultado = svc.analisar_governado(
        provider='ollama_gateway',
        contexto='validar provider local governado',
        entrada='analisar codigo sem dado sensivel',
        usuario={'sub': 'gateway-provider@example.com'},
        correlation_id='codex-gateway-001',
        publicar_no_reqsys=False,
    )

    assert resultado['bloqueado'] is False
    assert resultado['provider'] == 'ollama_gateway'
    assert resultado['resultado'] == 'resposta via gateway local'
    assert resultado['score_confianca'] >= 85
    assert chamadas['url'] == 'http://gateway.local:8008/v1/chat'
    assert chamadas['headers']['X-API-Key'] == 'test-key'
    assert chamadas['payload']['source'] == 'reqsys-codex-local-online'
    assert chamadas['payload']['correlation_id'] == 'codex-gateway-001'


def test_rate_limit_bloqueia_excesso():
    usuario = {'sub': 'rate-limit@example.com'}
    ultimo = None
    for i in range(25):
        ultimo = analisar_governado(
            provider='mock',
            contexto='ctx',
            entrada=f'entrada {i}',
            usuario=usuario,
            correlation_id=f'codex-rate-{i}',
            publicar_no_reqsys=False,
        )
    assert ultimo is not None
    assert ultimo['bloqueado'] is True
    assert ultimo['motivo'] == 'rate_limit'


def test_auditoria_persistente_e_resumo_operacional():
    db = SessionLocal()
    try:
        resultado = analisar_governado(
            provider='mock',
            contexto='dashboard operacional codex',
            entrada='registrar auditoria persistente',
            usuario={'sub': 'audit@example.com'},
            correlation_id='codex-audit-001',
            publicar_no_reqsys=False,
            db=db,
        )
        resumo = resumo_operacional(db)
    finally:
        db.close()

    assert resultado['bloqueado'] is False
    assert resumo['total'] >= 1
    assert resumo['concluidos'] >= 1
    assert resumo['score_confianca_medio'] >= 0
    assert 'mock' in resumo['por_provider']
