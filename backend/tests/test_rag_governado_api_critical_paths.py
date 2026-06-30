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
    assert 'llamaIndexDisponivel' in data
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
