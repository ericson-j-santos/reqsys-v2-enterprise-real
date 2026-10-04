"""Contratos preventivos da recuperação do PR #44 (Arquitetura Viva)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_superficies_canonicas_da_arquitetura_viva_estao_registradas():
    for path in (
        "frontend/src/router/index.js",
        "frontend/src/constants/navCatalog.js",
        "frontend/src/constants/rotasResponsivas.js",
        "governance/reqsys-360/route-responsibilities.json",
    ):
        assert "/arquitetura-viva" in read(path)
    view = read("frontend/src/views/ArquiteturaVivaView.vue")
    assert 'data-testid="route-arquitetura-viva"' in view
    assert 'data-testid="architecture-live-canvas"' in view
    assert 'data-testid="architecture-live-inspector"' in view

def test_engine_mermaid_permanece_fail_closed_e_sanitiza_labels():
    source = read("src/platform/architecture-visualization/generators/mermaid-generator.ts")
    assert "if (!diagram.sources?.length)" in source
    assert "if (!diagram.environment)" in source
    assert ".replace(/[\\r\\n]+/g, ' ')" in source
    assert ".replace(/[\\[\\]{}<>]/g, '')" in source
    assert "%% confidence:" in source
    assert "%% hash:" in source

def test_ui_nao_afirma_integracao_runtime_que_ainda_nao_existe():
    view = read("frontend/src/views/ArquiteturaVivaView.vue")
    assert "{ nome: 'Execução real integrada', ok: false }" in view
    assert "execução real e OpenTelemetry ainda não estão integrados" in view


def test_ui_usa_rotulos_claros_nos_nos_principais():
    view = read("frontend/src/views/ArquiteturaVivaView.vue")
    assert "label: 'Versão de código'" in view
    assert "label: 'Solicitação de integração'" in view
    assert "label: 'Verificações automáticas'" in view
    assert "label: 'Indicadores'" in view
