from uuid import uuid4


def _headers(auth_headers, chave=None, correlation_id=None):
    return {
        **auth_headers,
        'Idempotency-Key': chave or f'idem-{uuid4()}',
        'X-Correlation-Id': correlation_id or f'corr-{uuid4()}',
    }


def _payload(registros=None, versao=1):
    return {
        'origem': 'PENTAHO',
        'processo': 'TESTE_INTEGRACAO',
        'versaoEntrada': versao,
        'dataReferencia': '2026-08-29',
        'lote': f'lote-{uuid4()}',
        'registros': registros if registros is not None else [{'produto': 10001, 'canal': 'WEB'}],
    }


def test_recebe_processa_e_consulta_lote(client, auth_headers):
    resposta = client.post('/api/integracoes/pentaho/lotes', json=_payload(), headers=_headers(auth_headers))
    assert resposta.status_code == 202
    criado = resposta.json()
    assert criado['duplicado'] is False
    assert criado['loteId']
    assert criado['correlationId']

    consulta = client.get(criado['consulta'], headers=auth_headers)
    assert consulta.status_code == 200
    status = consulta.json()
    assert status['status'] == 'CONCLUIDO'
    assert status['registrosRecebidos'] == 1
    assert status['registrosAceitos'] == 1
    assert status['registrosRejeitados'] == 0
    assert status['tentativas'] == 1


def test_idempotency_key_nao_cria_lote_duplicado(client, auth_headers):
    chave = f'idem-{uuid4()}'
    headers = _headers(auth_headers, chave=chave)
    primeiro = client.post('/api/integracoes/pentaho/lotes', json=_payload(), headers=headers)
    segundo = client.post('/api/integracoes/pentaho/lotes', json=_payload(), headers=headers)

    assert primeiro.status_code == 202
    assert segundo.status_code == 202
    assert segundo.json()['duplicado'] is True
    assert segundo.json()['loteId'] == primeiro.json()['loteId']


def test_lote_sem_registro_util_vai_para_quarentena_e_pode_reprocessar(client, auth_headers):
    criado = client.post(
        '/api/integracoes/pentaho/lotes',
        json=_payload(registros=[{}]),
        headers=_headers(auth_headers),
    )
    assert criado.status_code == 202
    lote_id = criado.json()['loteId']

    consulta = client.get(f'/api/integracoes/pentaho/lotes/{lote_id}', headers=auth_headers)
    assert consulta.status_code == 200
    assert consulta.json()['status'] == 'QUARENTENA'
    assert consulta.json()['erroCodigo'] == 'FALHA_PROCESSAMENTO_ADAPTADOR'

    reprocessado = client.post(f'/api/integracoes/pentaho/lotes/{lote_id}/reprocessar', headers=auth_headers)
    assert reprocessado.status_code == 202

    consulta_final = client.get(f'/api/integracoes/pentaho/lotes/{lote_id}', headers=auth_headers)
    assert consulta_final.status_code == 200
    assert consulta_final.json()['status'] == 'QUARENTENA'
    assert consulta_final.json()['tentativas'] == 2


def test_rejeita_versao_de_contrato_nao_suportada(client, auth_headers):
    resposta = client.post(
        '/api/integracoes/pentaho/lotes',
        json=_payload(versao=99),
        headers=_headers(auth_headers),
    )
    assert resposta.status_code == 422
    assert 'Versão de entrada não suportada' in resposta.json()['detail']


def test_exige_cabecalhos_de_rastreabilidade(client, auth_headers):
    resposta = client.post('/api/integracoes/pentaho/lotes', json=_payload(), headers=auth_headers)
    assert resposta.status_code == 422


def test_dashboard_retorna_estrutura_operacional(client, auth_headers):
    resposta = client.get('/api/integracoes/pentaho/dashboard', headers=auth_headers)
    assert resposta.status_code == 200
    payload = resposta.json()
    assert set(payload['contagens']) == {'recebidos', 'concluidos', 'processando', 'quarentena'}
    assert isinstance(payload['processos'], list)
    assert isinstance(payload['lotesRecentes'], list)
