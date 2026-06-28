"""Testes de caminhos críticos — cliente Gemini/Groq e fallback."""

from unittest.mock import patch

import pytest

from app.services.gemini import (
    GeminiIndisponivel,
    _gerar,
    _gerar_com_fallback,
    _gerar_groq,
    classificar_urgencia,
    resumir_requisito,
    sugerir_descricao,
)
from app.services.rag_governado import responder_rag_governado


def test_gerar_sem_api_key():
    with pytest.raises(GeminiIndisponivel, match="GEMINI_API_KEY"):
        _gerar("", "gemini-2.0-flash", "prompt")


def test_gerar_pacote_gemini_ausente():
    with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)) if name == "google.generativeai" else __import__(name, *args, **kwargs)):
        with pytest.raises(GeminiIndisponivel, match="não instalado"):
            _gerar("key", "gemini-2.0-flash", "prompt")


def test_gerar_groq_sem_api_key():
    with pytest.raises(GeminiIndisponivel, match="GROQ_API_KEY"):
        _gerar_groq("", "llama", "prompt")


def test_gerar_groq_pacote_ausente():
    with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)) if name == "groq" else __import__(name, *args, **kwargs)):
        with pytest.raises(GeminiIndisponivel, match="não instalado"):
            _gerar_groq("key", "llama", "prompt")


def test_resumir_e_sugerir_descricao_usam_fallback():
    with patch("app.services.gemini._gerar_com_fallback", return_value=("texto gerado", "gemini")) as mock_fallback:
        resumo, provedor_resumo = resumir_requisito("t", "d", "k", "model")
        descricao, provedor_desc = sugerir_descricao("t", "TI", "ReqSys", "k", "model")

    assert resumo == "texto gerado"
    assert descricao == "texto gerado"
    assert provedor_resumo == "gemini"
    assert provedor_desc == "gemini"
    assert mock_fallback.call_count == 2


def test_gerar_com_fallback_usa_groq_quando_gemini_indisponivel():
    with patch("app.services.gemini._gerar", side_effect=GeminiIndisponivel("quota")):
        with patch("app.services.gemini._gerar_groq", return_value="resposta groq") as groq_mock:
            texto, provedor = _gerar_com_fallback("g-key", "gemini", "q-key", "llama", "prompt")

    assert texto == "resposta groq"
    assert provedor == "groq"
    groq_mock.assert_called_once()


def test_classificar_urgencia_parseia_resposta():
    resposta = "URGENCIA: alta\nJUSTIFICATIVA: Impacto operacional elevado."
    with patch("app.services.gemini._gerar_com_fallback", return_value=(resposta, "gemini")):
        classificacao, provedor = classificar_urgencia("titulo", "desc", "k", "model")

    assert classificacao.urgencia == "alta"
    assert provedor == "gemini"


def test_responder_rag_sem_evidencia_bloqueia():
    resposta = responder_rag_governado("pergunta sem termos compativeis xyz", [], correlation_id="corr-rag")

    assert resposta.status_fluxo == "SEM_EVIDENCIA_BLOQUEADO"
    assert resposta.fontes == []
