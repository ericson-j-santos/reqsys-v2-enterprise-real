from app.services.rag_governado import normalizar_documentos, responder_rag_governado


def test_rag_responde_somente_com_fontes_recuperadas():
    documentos = normalizar_documentos([
        {
            'id': 'gov-001',
            'titulo': 'Governanca RAG',
            'conteudo': 'RAG corporativo deve responder com fontes, correlation_id, auditoria e bloqueio sem evidencia.',
            'origem': 'teste',
        }
    ])

    resposta = responder_rag_governado('Como o RAG corporativo deve responder?', documentos, correlation_id='teste-123')

    assert resposta.correlation_id == 'teste-123'
    assert resposta.status_fluxo == 'COM_FONTES'
    assert resposta.fontes
    assert 'fontes recuperadas' in resposta.resposta.lower()


def test_rag_bloqueia_resposta_sem_evidencia():
    documentos = normalizar_documentos([
        {
            'id': 'doc-001',
            'titulo': 'Documento sem relacao',
            'conteudo': 'Este documento fala apenas sobre pipeline operacional.',
        }
    ])

    resposta = responder_rag_governado('Qual a politica de ferias?', documentos, correlation_id='teste-456')

    assert resposta.status_fluxo == 'SEM_EVIDENCIA_BLOQUEADO'
    assert resposta.fontes == []
    assert 'evidência suficiente' in resposta.resposta


def test_rag_mascara_pii_em_documentos():
    documentos = normalizar_documentos([
        {
            'id': 'pii-001',
            'titulo': 'Contato',
            'conteudo': 'Contato do usuario: pessoa@example.com e CPF 123.456.789-09.',
        }
    ])

    resposta = responder_rag_governado('Qual o contato do usuario?', documentos, correlation_id='teste-789')

    assert resposta.status_fluxo == 'COM_FONTES'
    assert 'pessoa@example.com' not in resposta.fontes[0].trecho
    assert '123.456.789-09' not in resposta.fontes[0].trecho
    assert '[DADO_MASCARADO]' in resposta.fontes[0].trecho
