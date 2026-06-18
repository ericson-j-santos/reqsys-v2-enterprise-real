"""
Testes do modulo Processos.

Cobertura minima:
- pre-validacao aprovada;
- pre-validacao bloqueada;
- inicio de processo aprovado;
- inicio de processo bloqueado;
- payload invalido.
"""


def _payload_valido(**overrides):
    payload = {
        'tipo_processo': 'demanda',
        'acao': 'iniciar',
        'usuario': {
            'id': 'usuario-teste',
            'perfil': 'admin',
            'escopos': ['demanda:iniciar'],
        },
        'dados': {
            'titulo': 'Demanda de teste automatizado',
            'descricao': 'Descricao suficiente para validar o fluxo automatizado.',
            'responsavel': 'time-reqsys',
            'prioridade': 'alta',
            'evidencias': [{'tipo': 'email', 'referencia': 'MSG-001'}],
            'criterio_aceite': 'Dado um contexto valido, quando iniciar, entao o processo deve ser criado.',
            'valor_negocio': 'Reduzir retrabalho operacional.',
        },
        'correlation_id': 'corr-processos-001',
    }
    payload.update(overrides)
    return payload


def test_pre_validar_demanda_aprovada(client):
    resp = client.post('/v1/processos/pre-validar', json=_payload_valido())

    assert resp.status_code == 200
    data = resp.json()
    assert data['apto_para_iniciar'] is True
    assert data['status_validacao'] == 'aprovado'
    assert data['score_prontidao'] == 100
    assert data['correlation_id'] == 'corr-processos-001'


def test_pre_validar_sem_permissao_bloqueia(client):
    payload = _payload_valido(usuario={
        'id': 'usuario-sem-escopo',
        'perfil': 'analista',
        'escopos': [],
    })

    resp = client.post('/v1/processos/pre-validar', json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data['apto_para_iniciar'] is False
    assert data['status_validacao'] == 'bloqueado'
    assert any(b['codigo'] == 'PERMISSAO_INSUFICIENTE' for b in data['bloqueios'])


def test_iniciar_processo_aprovado_retorna_envelope(client):
    resp = client.post(
        '/v1/processos/iniciar',
        json=_payload_valido(),
        headers={'X-Correlation-ID': 'corr-header-processos'},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['meta']['correlation_id'] == 'corr-header-processos'
    data = body['data']
    assert data['processo_id'].startswith('DEMANDA-')
    assert data['status'] == 'iniciado'
    assert data['tipo_processo'] == 'demanda'


def test_iniciar_processo_bloqueado_retorna_422(client):
    payload = _payload_valido()
    payload['dados'].pop('criterio_aceite')

    resp = client.post('/v1/processos/iniciar', json=payload)

    assert resp.status_code == 422
    detail = resp.json()['detail']
    assert detail['apto_para_iniciar'] is False
    assert any(b['codigo'] == 'CRITERIO_ACEITE_AUSENTE' for b in detail['bloqueios'])


def test_processos_payload_invalido_retorna_422(client):
    resp = client.post('/v1/processos/pre-validar', json={'acao': 'iniciar'})

    assert resp.status_code == 422
