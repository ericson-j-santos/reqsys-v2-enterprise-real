from uuid import uuid4


def _criar_requisito(client, headers):
    sufixo = uuid4().hex[:8]
    resposta = client.post(
        '/v1/requisitos',
        headers=headers,
        json={
            'titulo': f'Requisito gestão TI {sufixo}',
            'descricao': 'Descrição válida com critério de aceite para testar o vínculo canônico.',
            'urgencia': 'media',
            'area': 'tecnologia',
            'sistema': 'reqsys',
            'solicitante': 'teste_integracao',
            'impacto_regulatorio': False,
        },
    )
    assert resposta.status_code == 200
    return resposta.json()['data']


def test_catalogo_vinculo_painel_e_consulta_power_bi(client, auth_headers):
    sufixo = uuid4().hex[:8].upper()
    headers = {**auth_headers, 'X-Correlation-Id': f'corr-gestao-ti-{sufixo.lower()}'}

    servico_resposta = client.post(
        '/api/requisitos/gestao-ti/servicos',
        headers=headers,
        json={
            'codigo': f'REQSYSTESTE_{sufixo}',
            'nome': 'ReqSys Teste Canônico',
            'descricao': 'Serviço criado pelo teste de contrato.',
            'criticidade': 'alta',
            'responsavel_tecnico': 'Equipe ReqSys',
            'responsavel_negocio': 'Gestão de Produtos',
        },
    )
    assert servico_resposta.status_code == 201
    servico = servico_resposta.json()['data']
    assert len(servico['servico_id']) == 36
    assert servico['versao_catalogo'] == 1

    requisito = _criar_requisito(client, headers)
    vinculo_resposta = client.post(
        '/api/requisitos/gestao-ti/vinculos',
        headers=headers,
        json={'requisito_id': requisito['id'], 'servico_id': servico['servico_id']},
    )
    assert vinculo_resposta.status_code == 201
    assert vinculo_resposta.json()['data']['idempotente'] is False

    repeticao = client.post(
        '/api/requisitos/gestao-ti/vinculos',
        headers=headers,
        json={'requisito_id': requisito['id'], 'servico_id': servico['servico_id']},
    )
    assert repeticao.status_code == 201
    assert repeticao.json()['data']['idempotente'] is True

    consulta = client.get('/api/requisitos/gestao-ti/consulta/requisitos-servicos', headers=headers)
    assert consulta.status_code == 200
    assert consulta.json()['meta']['read_only'] is True
    assert any(item['requisito_id'] == requisito['id'] for item in consulta.json()['data'])

    painel = client.get('/api/requisitos/gestao-ti/painel', headers=headers)
    assert painel.status_code == 200
    assert painel.json()['data']['catalogo']['requisitos_vinculados'] >= 1
    assert 'fila' in painel.json()['data']


def test_mutacoes_exigem_autenticacao_administrativa(client):
    resposta = client.post(
        '/api/requisitos/gestao-ti/servicos',
        json={
            'codigo': 'SEM_AUTENTICACAO',
            'nome': 'Serviço não autorizado',
            'criticidade': 'baixa',
            'responsavel_tecnico': 'Equipe',
            'responsavel_negocio': 'Negócio',
        },
    )
    assert resposta.status_code == 401
