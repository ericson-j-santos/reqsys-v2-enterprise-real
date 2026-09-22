from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api.vba_legacy import analyze_vba_upload
from app.services.vba_semantic_analyzer import analyze_vba_semantics


SOURCE = """Sub Processar(ByVal codigo As String)
    entrada = Worksheets("Entrada").Range("B2").Value
    If entrada = "PENDENTE" Then status = "ANALISAR"
    Open "resultado.txt" For Output As #1
    Print #1, status
    mensagem.Send
    query = "QUERY_SANITIZED"
    conexao.Execute query
    Worksheets("Saida").Range("C5").Value = status
End Sub
"""


def _upload(nome: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(SOURCE.encode("utf-8")),
        filename=nome,
        headers=Headers({"content-type": "text/plain"}),
    )


@pytest.mark.parametrize("ext", [".bas", ".cls", ".frm", ".vba", ".txt"])
async def test_extensoes_de_fonte_usam_analise_estatica(ext: str):
    response = await analyze_vba_upload(
        arquivo=_upload(f"modulo{ext}"),
        user={"papel": "admin"},
        x_correlation_id=f"corr-vba-{ext[1:]}",
    )
    assert response["success"] is True
    assert response["data"]["analysis_type"] == "static_only"
    assert response["data"]["execution_performed"] is False
    assert response["meta"]["source_persisted"] is False


def test_linhagem_cobre_origens_regras_e_destinos_sanitizados():
    result = analyze_vba_semantics(SOURCE, file_name="rastreabilidade.bas")
    semantic = result["semantic_analysis"]
    flow = semantic["data_flow"]

    node_types = {node["type"] for node in flow["nodes"]}
    sink_types = {sink["type"] for sink in flow["sinks"]}

    assert "parameter" in node_types
    assert "excel_input" in node_types
    assert {"excel_output", "database_sink", "file_sink", "message_sink"} <= sink_types
    assert result["summary"]["business_rules"] >= 1
    assert semantic["test_candidates"]
    assert all(item["requires_human_validation"] is True for item in semantic["test_candidates"])
    assert semantic["execution_performed"] is False
    assert semantic["source_persisted"] is False
