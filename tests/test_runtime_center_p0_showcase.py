import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "docs/public-showcase/reqsys-linkedin/runtime-center"


def test_runtime_center_showcase_declara_que_nao_e_evidencia_operacional() -> None:
    html = (SHOWCASE / "index.html").read_text(encoding="utf-8")
    readme = (SHOWCASE / "README.md").read_text(encoding="utf-8")
    contract = json.loads((SHOWCASE / "runtime-health.contract.json").read_text(encoding="utf-8"))

    assert "Demonstração estática" in html
    assert "não representam o runtime atual" in html
    assert "showcase estático" in readme.lower()
    assert contract["mode"] == "illustrative"
    assert contract["operational_evidence"] is False


def test_runtime_center_showcase_preserva_blocos_visuais_p0() -> None:
    html = (SHOWCASE / "index.html").read_text(encoding="utf-8")

    assert "Runtime Operational Center P0" in html
    assert "Health cards operacionais" in html
    assert "Linha do tempo viva" in html
    assert "Indicadores executivos P0" in html
    assert "Arquitetura viva navegavel" in html
    assert "Centro de incidentes P0" in html


def test_contrato_aponta_para_fontes_operacionais_reais() -> None:
    contract = json.loads((SHOWCASE / "runtime-health.contract.json").read_text(encoding="utf-8"))

    assert "/api/runtime/health" in contract["evidence_sources"]
    assert "/api/runtime/readiness" in contract["evidence_sources"]
    assert "/api/runtime/metrics" in contract["evidence_sources"]
