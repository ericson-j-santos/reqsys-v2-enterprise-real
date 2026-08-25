from app.services.rag_governado import criar_chunks, normalizar_documentos, recuperar_fontes_semanticas, responder_rag_governado


def test_rag_responde_somente_com_fontes_recuperadas():
    documentos = normalizar_documentos([{'id': 'gov-001', 'titulo': 'Governanca RAG', 'conteudo': 'RAG corporativo deve responder com fontes, correlation_id, auditoria e bloqueio sem evidencia.', 'origem': 'teste'}])
    resposta = responder_rag_governado('Como o RAG corporativo deve responder?', documentos, correlation_id='teste-123')
    assert resposta.correlation_id == 'teste-123'
    assert resposta.status_fluxo == 'COM_FONTES'
    assert resposta.fontes
    assert 'fontes recuperadas' in resposta.resposta.lower()
    assert resposta.engine == 'semantic-hash-embedding+memory-vector-store-v1'


def test_rag_bloqueia_resposta_sem_evidencia():
    documentos = normalizar_documentos([{'id': 'doc-001', 'titulo': 'Documento sem relacao', 'conteudo': 'Este documento fala apenas sobre pipeline operacional.'}])
    resposta = responder_rag_governado('Qual a politica de ferias?', documentos, correlation_id='teste-456')
    assert resposta.status_fluxo == 'SEM_EVIDENCIA_BLOQUEADO'
    assert resposta.fontes == []
    assert 'evidência suficiente' in resposta.resposta


def test_rag_mascara_pii_em_documentos():
    documentos = normalizar_documentos([{'id': 'pii-001', 'titulo': 'Contato', 'conteudo': 'Contato do usuario: pessoa@example.com e CPF 123.456.789-09.'}])
    resposta = responder_rag_governado('Qual o contato do usuario?', documentos, correlation_id='teste-789')
    assert resposta.status_fluxo == 'COM_FONTES'
    assert 'pessoa@example.com' not in resposta.fontes[0].trecho
    assert '123.456.789-09' not in resposta.fontes[0].trecho
    assert '[DADO_MASCARADO]' in resposta.fontes[0].trecho


def test_chunking_e_versionado_e_tem_sobreposicao():
    documentos = normalizar_documentos([{'id': 'doc', 'titulo': 'Longo', 'conteudo': 'arquitetura ' * 150}])
    chunks = criar_chunks(documentos, tamanho=300, sobreposicao=50)
    assert len(chunks) > 1
    assert all(chunk.versao for chunk in chunks)
    assert len({chunk.versao for chunk in chunks}) == 1
    assert chunks[0].id != chunks[1].id


def test_retriever_semantico_prioriza_conteudo_relacionado():
    documentos = normalizar_documentos([
        {'id': 'rag', 'titulo': 'RAG', 'conteudo': 'embeddings vetoriais recuperam documentos semanticamente relevantes para a pergunta'},
        {'id': 'deploy', 'titulo': 'Deploy', 'conteudo': 'pipeline publica containers e executa rollback de aplicacao'},
    ])
    fontes = recuperar_fontes_semanticas('Como recuperar documentos com embeddings vetoriais?', documentos, top_k=1)
    assert fontes
    assert fontes[0].titulo == 'RAG'
    assert fontes[0].score > 0


def test_chunking_rejeita_configuracao_invalida():
    documentos = normalizar_documentos([{'conteudo': 'conteudo'}])
    try:
        criar_chunks(documentos, tamanho=100, sobreposicao=100)
    except ValueError as exc:
        assert 'invalida' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError')
