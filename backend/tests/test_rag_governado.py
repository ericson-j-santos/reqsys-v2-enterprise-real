from app.core.config import settings
from app.services.rag_governado import (
    PROVIDER_HASH_LOCAL,
    ChunkRAG,
    criar_chunks,
    gerar_resposta_llm,
    indexar_chunks_persistentes,
    normalizar_documentos,
    recuperar_fontes_semanticas,
    recuperar_fontes_semanticas_persistidas,
    resolver_provider_embedding_ativo,
    responder_rag_governado,
    responder_rag_governado_persistido,
    VectorStoreMemoria,
)


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


def test_indexar_chunks_persistentes_grava_e_e_idempotente(db_session):
    documentos = normalizar_documentos([{'id': 'persist-doc', 'titulo': 'Retencao', 'conteudo': 'Politica de retencao de dados de auditoria por cinco anos.'}])

    total_primeira = indexar_chunks_persistentes(db_session, documentos)
    total_segunda = indexar_chunks_persistentes(db_session, documentos)

    assert total_primeira >= 1
    assert total_segunda == total_primeira

    fontes = recuperar_fontes_semanticas_persistidas(db_session, 'Qual a politica de retencao de dados?')
    assert fontes
    assert fontes[0].titulo == 'Retencao'


def test_gerar_resposta_llm_retorna_none_sem_credencial_configurada(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_llm_provider', '')
    monkeypatch.setattr(settings, 'reqsys_rag_llm_api_key', '')

    from app.services.rag_governado import FonteRAG

    fontes = [FonteRAG(id='1', titulo='Doc', origem='a', score=0.9, trecho='trecho')]
    assert gerar_resposta_llm('pergunta', fontes) is None


def test_gerar_resposta_llm_provider_nao_suportado_retorna_none(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_llm_provider', 'provider-inexistente')
    monkeypatch.setattr(settings, 'reqsys_rag_llm_api_key', 'chave-fake')

    from app.services.rag_governado import FonteRAG

    fontes = [FonteRAG(id='1', titulo='Doc', origem='a', score=0.9, trecho='trecho')]
    assert gerar_resposta_llm('pergunta', fontes) is None


def test_gerar_resposta_llm_chama_gateway_e_retorna_texto(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_llm_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_llm_api_key', 'chave-fake')
    monkeypatch.setattr(settings, 'reqsys_rag_llm_model', 'gpt-teste')

    from app.services.rag_governado import FonteRAG

    class GatewayFake:
        def gerar_openai(self, *, api_key, model, prompt, system_prompt):
            assert api_key == 'chave-fake'
            assert model == 'gpt-teste'
            assert 'pergunta' in prompt.lower()
            return 'resposta gerada pelo modelo'

    fontes = [FonteRAG(id='1', titulo='Doc', origem='a', score=0.9, trecho='trecho relevante')]
    resultado = gerar_resposta_llm('Qual a pergunta?', fontes, gateway=GatewayFake())
    assert resultado == 'resposta gerada pelo modelo'


def test_gerar_resposta_llm_falha_na_chamada_retorna_none(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_llm_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_llm_api_key', 'chave-fake')

    from app.services.rag_governado import FonteRAG

    class GatewayQuebrado:
        def gerar_openai(self, **kwargs):
            raise RuntimeError('falha simulada de rede')

    fontes = [FonteRAG(id='1', titulo='Doc', origem='a', score=0.9, trecho='trecho')]
    assert gerar_resposta_llm('pergunta', fontes, gateway=GatewayQuebrado()) is None


def test_responder_rag_governado_usa_llm_quando_configurado(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_llm_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_llm_api_key', 'chave-fake')

    import app.services.rag_governado as modulo

    monkeypatch.setattr(modulo, 'gerar_resposta_llm', lambda pergunta, fontes, **kw: 'resposta em linguagem natural')

    documentos = normalizar_documentos([{'id': 'gov-002', 'titulo': 'Governanca RAG', 'conteudo': 'RAG corporativo deve responder com fontes e auditoria.', 'origem': 'teste'}])
    resposta = responder_rag_governado('Como o RAG corporativo deve responder?', documentos, correlation_id='teste-llm-001')

    assert resposta.status_fluxo == 'COM_FONTES'
    assert 'resposta em linguagem natural' in resposta.resposta
    assert resposta.engine == 'semantic-hash-embedding+memory-vector-store-v1+llm-openai'


def test_resolver_provider_embedding_ativo_sem_configuracao_usa_local(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', '')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', '')
    assert resolver_provider_embedding_ativo() == PROVIDER_HASH_LOCAL


def test_resolver_provider_embedding_ativo_provider_nao_suportado_usa_local(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'cohere')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')
    assert resolver_provider_embedding_ativo() == PROVIDER_HASH_LOCAL


def test_resolver_provider_embedding_ativo_sem_api_key_usa_local(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', '')
    assert resolver_provider_embedding_ativo() == PROVIDER_HASH_LOCAL


def test_resolver_provider_embedding_ativo_configurado_usa_externo(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')
    assert resolver_provider_embedding_ativo() == 'openai'


class GatewayEmbeddingFake:
    def __init__(self, vetores):
        self._vetores = vetores
        self.chamadas = 0

    def gerar_embeddings_openai(self, *, api_key, model, textos):
        self.chamadas += 1
        assert api_key == 'chave-fake'
        return [self._vetores[texto] for texto in textos]


class GatewayEmbeddingQuebrado:
    def gerar_embeddings_openai(self, **kwargs):
        raise RuntimeError('falha simulada de rede')


def test_vector_store_memoria_usa_provider_externo_configurado(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')

    chunk = ChunkRAG(id='c1', documento_id='d1', titulo='Doc', origem='a', conteudo='texto', indice=0, versao='v1')
    gateway = GatewayEmbeddingFake({'Doc texto': [1.0, 0.0], 'pergunta': [1.0, 0.0]})

    store = VectorStoreMemoria([chunk], gateway=gateway)
    fontes = store.buscar('pergunta')

    assert fontes
    assert fontes[0].id == 'c1'
    assert gateway.chamadas == 2


def test_vector_store_memoria_cai_para_local_quando_provider_externo_falha_na_indexacao(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')

    chunk = ChunkRAG(id='c1', documento_id='d1', titulo='Governanca', origem='a', conteudo='politica de governanca corporativa', indice=0, versao='v1')
    store = VectorStoreMemoria([chunk], gateway=GatewayEmbeddingQuebrado())

    fontes = store.buscar('politica de governanca')

    assert fontes
    assert fontes[0].id == 'c1'


def test_vector_store_memoria_sem_fontes_falha_na_consulta_nao_inventa_evidencia(monkeypatch):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')

    chunk = ChunkRAG(id='c1', documento_id='d1', titulo='Doc', origem='a', conteudo='texto', indice=0, versao='v1')
    gateway = GatewayEmbeddingFake({'Doc texto': [1.0, 0.0]})
    store = VectorStoreMemoria([chunk], gateway=gateway)

    class GatewayFalhaSoNaConsulta:
        def gerar_embeddings_openai(self, *, api_key, model, textos):
            raise RuntimeError('falha simulada na consulta')

    store._gateway = GatewayFalhaSoNaConsulta()
    assert store.buscar('pergunta qualquer') == []


def test_indexar_e_recuperar_persistente_com_provider_externo(monkeypatch, db_session):
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')

    documentos = normalizar_documentos([{'id': 'ext-doc', 'titulo': 'Retencao Externa', 'conteudo': 'Politica de retencao de dados via provider externo.'}])
    gateway = GatewayEmbeddingFake({
        'Retencao Externa Politica de retencao de dados via provider externo.': [1.0, 0.0],
        'Qual a politica de retencao externa?': [1.0, 0.0],
    })

    indexar_chunks_persistentes(db_session, documentos, gateway=gateway)
    fontes = recuperar_fontes_semanticas_persistidas(db_session, 'Qual a politica de retencao externa?', gateway=gateway)

    assert fontes
    assert fontes[0].titulo == 'Retencao Externa'


def test_recuperar_persistente_nao_mistura_providers_diferentes(monkeypatch, db_session):
    documentos = normalizar_documentos([{'id': 'local-doc', 'titulo': 'Indexado Localmente', 'conteudo': 'Conteudo indexado com o embedding local padrao.'}])
    indexar_chunks_persistentes(db_session, documentos)

    monkeypatch.setattr(settings, 'reqsys_rag_embedding_provider', 'openai')
    monkeypatch.setattr(settings, 'reqsys_rag_embedding_api_key', 'chave-fake')
    gateway = GatewayEmbeddingFake({'Qual o conteudo indexado?': [1.0, 0.0]})

    fontes = recuperar_fontes_semanticas_persistidas(db_session, 'Qual o conteudo indexado?', gateway=gateway)

    assert fontes == []


def test_responder_rag_governado_persistido_bloqueia_sem_evidencia(db_session):
    resposta = responder_rag_governado_persistido(db_session, 'Pergunta sem nenhuma correspondencia indexada xyzabc123', correlation_id='teste-persist-vazio')

    assert resposta.status_fluxo == 'SEM_EVIDENCIA_BLOQUEADO'
    assert resposta.engine == 'semantic-hash-embedding+postgres-vector-store-v1'
    assert resposta.fontes == []
