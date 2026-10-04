"""Testes do contrato canônico de coleta e geração de requisitos."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload_completo(**alteracoes):
    payload = {
        'versao_contrato': '1.0.0',
        'chave_idempotencia': f'teste-{uuid4()}',
        'origem': 'reqsys',
        'solicitante': 'Squad de Produto',
        'area': 'Tecnologia',
        'sistema': 'ReqSys',
        'tipo_demanda': 'nova_funcionalidade',
        'problema': 'As solicitações chegam por canais diferentes e perdem contexto durante o refinamento.',
        'objetivo': 'Centralizar a entrada e gerar requisitos rastreáveis com qualidade mínima.',
        'usuario_afetado': 'analista de requisitos',
        'processo_atual': 'O solicitante envia texto livre e o analista reorganiza as informações manualmente.',
        'cenario_desejado': 'registrar a necessidade uma única vez em um formulário estruturado',
        'regras_negocio': [
            'Não gerar requisito quando a coleta estiver abaixo da pontuação mínima.',
            'A mesma chave de idempotência não pode criar requisitos duplicados.',
        ],
        'criterios_aceite': [
            'Ao enviar uma coleta completa, o sistema deve gerar um requisito com código rastreável.',
            'Ao repetir a mesma chave de idempotência, o sistema deve retornar o requisito já criado.',
        ],
        'dados_necessarios': ['área solicitante', 'sistema afetado'],
        'integracoes': ['Power Automate'],
        'restricoes': ['Não armazenar segredos ou tokens no formulário.'],
        'impacto_regulatorio': False,
        'urgencia': 'media',
        'referencia_externa': 'REF-TESTE-001',
        'observacoes': 'Massa sintética de teste.',
    }
    payload.update(alteracoes)
    return payload


def test_formulario_publica_contrato_declarativo():
    resposta = client.get('/api/requisitos/coleta/formulario')

    assert resposta.status_code == 200
    dados = resposta.json()['data']
    assert dados['versao_contrato'] == '1.0.0'
    assert dados['canais']['preferencial'] == 'reqsys'
    assert dados['regra_geracao']['pontuacao_minima'] == 80
    assert len(dados['secoes']) == 4
    assert any('senhas' in item.lower() for item in dados['instrucoes'])


def test_previsualizacao_gera_requisito_sem_persistir():
    resposta = client.post('/api/requisitos/coleta/previsualizar', json=_payload_completo())

    assert resposta.status_code == 200
    dados = resposta.json()['data']
    assert dados['persistido'] is False
    assert dados['avaliacao']['pronto_para_gerar'] is True
    assert dados['avaliacao']['pontuacao'] >= 80
    assert dados['requisito_proposto']['titulo'].startswith('Nova funcionalidade:')
    assert '## Critérios de aceite' in dados['requisito_proposto']['descricao']


def test_coleta_incompleta_permanece_em_refinamento():
    payload = _payload_completo(
        processo_atual=None,
        regras_negocio=[],
        criterios_aceite=['A saída deve ser verificável.'],
        dados_necessarios=[],
        integracoes=[],
        restricoes=[],
        referencia_externa=None,
    )

    previa = client.post('/api/requisitos/coleta/previsualizar', json=payload)
    assert previa.status_code == 200
    assert previa.json()['data']['avaliacao']['pronto_para_gerar'] is False

    geracao = client.post('/api/requisitos/coleta/gerar', json=payload)
    assert geracao.status_code == 422
    detalhe = geracao.json()['detail']
    assert detalhe['code'] == 'LEVANTAMENTO_REQUER_REFINAMENTO'
    assert detalhe['pontuacao'] < detalhe['pontuacao_minima']


def test_demanda_regulatoria_exige_referencia_rastreavel():
    payload = _payload_completo(
        impacto_regulatorio=True,
        referencia_externa=None,
    )

    resposta = client.post('/api/requisitos/coleta/gerar', json=payload)

    assert resposta.status_code == 422
    detalhe = resposta.json()['detail']
    assert detalhe['code'] == 'LEVANTAMENTO_REQUER_REFINAMENTO'
    assert any('referência externa' in item for item in detalhe['pendencias'])


def test_geracao_persiste_requisito_e_mantem_rastreabilidade():
    resposta = client.post(
        '/api/requisitos/coleta/gerar',
        json=_payload_completo(),
        headers={'x-correlation-id': 'corr-coleta-teste-001'},
    )

    assert resposta.status_code == 200
    dados = resposta.json()['data']
    requisito = dados['requisito']
    assert dados['persistido'] is True
    assert requisito['codigo'].startswith('REQ-')
    assert requisito['status'] == 'recebido'
    assert requisito['area'] == 'Tecnologia'
    assert requisito['sistema'] == 'ReqSys'
    assert '## Rastreabilidade' in requisito['descricao']


def test_idempotencia_impede_requisito_duplicado():
    chave = f'idempotencia-{uuid4()}'
    payload = _payload_completo(chave_idempotencia=chave)

    primeira = client.post('/api/requisitos/coleta/gerar', json=payload)
    segunda = client.post('/api/requisitos/coleta/gerar', json=payload)

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    primeiro = primeira.json()['data']['requisito']
    segundo = segunda.json()['data']['requisito']
    assert primeiro['id'] == segundo['id']
    assert primeiro['codigo'] == segundo['codigo']
    assert segunda.json()['data']['reutilizado'] is True


def test_chave_idempotencia_e_obrigatoria():
    payload = _payload_completo()
    del payload['chave_idempotencia']

    resposta = client.post('/api/requisitos/coleta/gerar', json=payload)

    assert resposta.status_code == 422
