from pathlib import Path

from scripts.export_openapi import gerar_openapi


def test_openapi_export_inclui_metadados_reqsys() -> None:
    schema = gerar_openapi()

    assert schema["info"]["title"] == "ReqSys Runtime API"
    assert schema["info"]["version"] == "0.7.0"
    assert schema["info"]["x-reqsys-contract-source"] == "runtime-fastapi"
    assert schema["info"]["x-reqsys-contract-mode"] == "canonical-generated"
    assert schema["info"]["x-reqsys-generated-by"] == "runtime/scripts/export_openapi.py"


def test_openapi_export_inclui_rotas_de_jobs() -> None:
    schema = gerar_openapi()

    assert "/api/jobs" in schema["paths"]
    assert "/api/jobs/{job_id}" in schema["paths"]
    assert "post" in schema["paths"]["/api/jobs"]
    assert "get" in schema["paths"]["/api/jobs/{job_id}"]


def test_openapi_canonico_esta_presente() -> None:
    path = Path(__file__).resolve().parents[2] / "docs-site/assets/openapi/reqsys-runtime-openapi-v0.7.0.json"

    assert path.exists()
