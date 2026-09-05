"""Bootstrap WSJF: substituir um WSJF.xlsx que o Graph recusa, em vez de reusar."""

import base64
import io
import struct
import zipfile
from pathlib import Path

import pytest

from scripts import bootstrap_wsjf_m365_dev as bootstrap

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "templates" / "wsjf" / "WSJF.xlsx.base64"
DRIVE = "b!drive-dev"
ITEM = "01ITEMWSJF"


def _template_bytes() -> bytes:
    return base64.b64decode(TEMPLATE.read_text(encoding="ascii"))


def _indice_quebrado(xlsx: bytes) -> bytes:
    dados = bytearray(xlsx)
    fim = dados.rfind(b"PK\x05\x06")
    (offset,) = struct.unpack_from("<I", dados, fim + 16)
    struct.pack_into("<I", dados, fim + 16, offset + 1836)
    return bytes(dados)


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, content=b""):
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {}
        self.content = content
        self.text = str(json_body or "")
        self.headers: dict[str, str] = {}

    def json(self):
        return self._json_body


class FakeClient:
    """Graph minimo para o caminho arquivo-existente do bootstrap."""

    def __init__(self, conteudo: bytes, workbook_ok_no_inicio: bool):
        self.conteudo = conteudo
        self.workbook_ok = workbook_ok_no_inicio
        self.calls: list[tuple[str, str]] = []
        self.enviados: dict[str, bytes] = {}

    def request(self, method, url, **kwargs):
        caminho = url.replace(bootstrap.GRAPH, "")
        self.calls.append((method, caminho))
        if caminho.endswith("/workbook/worksheets"):
            if self.workbook_ok:
                return FakeResponse(json_body={"value": [{"name": "Demandas"}]})
            return FakeResponse(
                status_code=400,
                json_body={"error": {"code": "unsupportedWorkbook", "message": "FileCorruptTryRepair"}},
            )
        if caminho.endswith("/content") and method == "GET":
            return FakeResponse(content=self.conteudo)
        if caminho.endswith("/content") and method == "PUT":
            self.enviados[caminho] = kwargs.get("content", b"")
            self.workbook_ok = True
            return FakeResponse(json_body={"id": ITEM, "name": bootstrap.FILE_NAME})
        return FakeResponse(json_body={"id": ITEM, "name": bootstrap.FILE_NAME})


def test_validate_template_aprova_o_template_versionado(tmp_path):
    arquivo = tmp_path / "WSJF.xlsx"
    arquivo.write_bytes(_template_bytes())

    bootstrap._validate_template(arquivo)


def test_validate_template_recusa_pacote_que_o_graph_nao_abre(tmp_path):
    arquivo = tmp_path / "WSJF.xlsx"
    arquivo.write_bytes(_indice_quebrado(_template_bytes()))

    with pytest.raises(bootstrap.BootstrapError, match="inválido para o Microsoft Graph"):
        bootstrap._validate_template(arquivo)


def test_arquivo_valido_e_reutilizado_sem_reescrita(tmp_path):
    template = tmp_path / "WSJF.xlsx"
    template.write_bytes(_template_bytes())
    client = FakeClient(_template_bytes(), workbook_ok_no_inicio=True)

    item, status, detalhe = bootstrap._find_or_create_file(client, "token", DRIVE, template)

    assert status == "reused"
    assert detalhe == {}
    assert item["id"] == ITEM
    assert not [rota for metodo, rota in client.calls if metodo == "PUT"]


def test_arquivo_recusado_pelo_graph_e_substituido_com_copia_de_seguranca(tmp_path):
    template = tmp_path / "WSJF.xlsx"
    template.write_bytes(_template_bytes())
    client = FakeClient(_indice_quebrado(_template_bytes()), workbook_ok_no_inicio=False)

    item, status, detalhe = bootstrap._find_or_create_file(client, "token", DRIVE, template)

    assert status == "replaced"
    assert item["id"] == ITEM
    assert detalhe["motivo"] == ["indice_zip_inconsistente"]
    assert detalhe["estrategia"] == "template_canonico"
    assert detalhe["linhas_preservadas"] == 0
    assert detalhe["backup"].startswith("WSJF.incompativel-")
    puts = [rota for metodo, rota in client.calls if metodo == "PUT"]
    assert len(puts) == 2
    assert f":/{detalhe['backup']}:/content" in puts[0]
    assert puts[1].endswith(f"/root:/{bootstrap.FILE_NAME}:/content")
    assert zipfile.is_zipfile(io.BytesIO(client.enviados[puts[1]]))
