from pathlib import Path

from app.reports.html_report import gerar_relatorio_html


def test_deve_gerar_relatorio_html(tmp_path: Path, resultado_verde):
    caminho = gerar_relatorio_html(
        resultados=[resultado_verde],
        caminho_saida=tmp_path / "relatorio.html",
    )

    assert caminho.exists()

    conteudo = caminho.read_text(encoding="utf-8")

    assert "Relatório Monitorador de APIs" in conteudo
    assert "api_teste" in conteudo
    assert "VERDE" in conteudo
