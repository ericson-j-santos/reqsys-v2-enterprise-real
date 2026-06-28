"""Testes de caminhos críticos — RAG governado."""

from pathlib import Path

from app.services.rag_governado import (
    carregar_documentos_do_diretorio,
    gerar_correlation_id,
    llama_index_disponivel,
    mascarar_pii,
    normalizar_documentos,
    recuperar_fontes_lexical,
)


def test_mascarar_pii_remove_cpf_e_email():
    texto = "Contato joao@empresa.com CPF 123.456.789-00"
    mascarado = mascarar_pii(texto)

    assert "[DADO_MASCARADO]" in mascarado
    assert "joao@empresa.com" not in mascarado


def test_normalizar_documentos_ignora_conteudo_vazio():
    documentos = normalizar_documentos(
        [
            {"id": "1", "titulo": "Vazio", "conteudo": "   "},
            {"content": "Politica de acesso corporativo", "title": "Politica"},
        ]
    )

    assert len(documentos) == 1
    assert documentos[0].titulo == "Politica"


def test_carregar_documentos_do_diretorio(tmp_path):
    arquivo = tmp_path / "guia.md"
    arquivo.write_text("Guia operacional de governanca", encoding="utf-8")

    documentos = carregar_documentos_do_diretorio(str(tmp_path))

    assert len(documentos) == 1
    assert documentos[0].origem == "guia.md"


def test_carregar_documentos_retorna_vazio_para_caminho_invalido():
    assert carregar_documentos_do_diretorio(None) == []
    assert carregar_documentos_do_diretorio(str(Path("/caminho/inexistente"))) == []


def test_recuperar_fontes_lexical_ranqueia_por_relevancia():
    from app.services.rag_governado import DocumentoRAG

    documentos = [
        DocumentoRAG(id="1", titulo="Governanca", conteudo="politica de governanca corporativa", origem="a"),
        DocumentoRAG(id="2", titulo="Outro", conteudo="conteudo irrelevante", origem="b"),
    ]

    fontes = recuperar_fontes_lexical("Qual a politica de governanca?", documentos)

    assert fontes
    assert fontes[0].id == "1"
    assert fontes[0].score > 0


def test_recuperar_fontes_lexical_sem_termos_retorna_vazio():
    from app.services.rag_governado import DocumentoRAG

    documentos = [DocumentoRAG(id="1", titulo="Doc", conteudo="abc", origem="a")]
    assert recuperar_fontes_lexical("??", documentos) == []


def test_trecho_relevante_usa_conteudo_curto_quando_sem_paragrafos():
    from app.services.rag_governado import DocumentoRAG, recuperar_fontes_lexical

    documentos = [DocumentoRAG(id="1", titulo="Doc", conteudo="texto", origem="a")]
    fontes = recuperar_fontes_lexical("texto", documentos)
    assert fontes[0].trecho == "texto"


def test_gerar_correlation_id_e_llama_index_flag():
    assert gerar_correlation_id().startswith("rag-")
    assert isinstance(llama_index_disponivel(), bool)
