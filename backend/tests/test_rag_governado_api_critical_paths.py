"""Testes de caminhos críticos — API RAG governado (/api/rag)."""

import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_rag_api.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')


def test_rag_health_retorna_status_operacional(client):
    response = client.get('/api/rag/health')
    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    data = body['data']
    assert data['service'] == 'rag-governado'
    assert data['status'] == 'ok'
    assert data['motorSemantico'] == 'semantic-hash-embedding+memory-vector-store-v1'
    assert data['modo'] == 'governado-com-fontes-obrigatorias'


def test_rag_perguntas_com_documentos_inline(client):
    response = client.post(
        '/api/rag/perguntas',
        headers={'X-Correlation-ID': 'corr-rag-api-001'},
        json={
            'pergunta': 'Qual a politica de governanca corporativa?',
            'top_k': 2,
            'documentos': [
                {
                    'id': 'doc-1',
                    'titulo': 'Governanca',
                    'conteudo': 'A politica de governanca corporativa define controles de acesso.',
                    'origem': 'teste',
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    data = body['data']
    assert data['evidenciaObrigatoria'] is True
    assert 'resposta' in data
    assert isinstance(data['fontes'], list)
    assert data['statusFluxo'] in {'COM_FONTES', 'SEM_FONTES', 'DEGRADADO', 'com_fontes', 'sem_fontes', 'degradado'}
    assert body['meta']['correlation_id'] == 'corr-rag-api-001'


def test_rag_indexar_persiste_chunks(client):
    response = client.post(
        '/api/rag/indexar',
        json={
            'documentos': [
                {
                    'id': 'doc-persist-1',
                    'titulo': 'Politica de Backup',
                    'conteudo': 'Backups sao executados diariamente com retencao de trinta dias.',
                    'origem': 'teste',
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body['success'] is True
    assert body['data']['documentosRecebidos'] == 1
    assert body['data']['chunksIndexados'] >= 1


def test_rag_perguntas_sem_documentos_usa_indice_persistido(client):
    indexar = client.post(
        '/api/rag/indexar',
        json={
            'documentos': [
                {
                    'id': 'doc-persist-2',
                    'titulo': 'Politica de Ferias',
                    'conteudo': 'Colaboradores podem solicitar ferias com trinta dias de antecedencia.',
                    'origem': 'teste',
                }
            ],
        },
    )
    assert indexar.status_code == 200

    response = client.post(
        '/api/rag/perguntas',
        headers={'X-Correlation-ID': 'corr-rag-persistido-001'},
        json={'pergunta': 'Como funciona a solicitacao de ferias?', 'top_k': 2, 'documentos': []},
    )
    assert response.status_code == 200
    data = response.json()['data']
    assert data['engine'] == 'semantic-hash-embedding+postgres-vector-store-v1'
    assert data['statusFluxo'] == 'COM_FONTES'
    assert data['fontes']
