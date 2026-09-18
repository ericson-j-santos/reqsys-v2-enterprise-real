"""Diagnostico/reparo do WSJF.xlsx do tenant e guarda de pre-instalacao."""

import base64
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.wsjf_planner_excel import require_wsjf_auth
from app.core.service_tokens import ServiceAuthContext
from app.main import app
from app.services import wsjf_excel_workbook as servico

BASE = '/v1/hub-lowcode/wsjf/planner-excel'
TEMPLATE = Path(__file__).resolve().parents[2] / 'templates' / 'wsjf' / 'WSJF.xlsx.base64'
DRIVE = 'b!drive-dev'
ITEM = '01ITEMWSJF'

client = TestClient(app)


@pytest.fixture
def auth_override():
    app.dependency_overrides[require_wsjf_auth] = lambda: ServiceAuthContext(ator='admin@teste', via_token=False)
    yield
    app.dependency_overrides.pop(require_wsjf_auth, None)


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, content=b''):
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {}
        self.content = content
        self.text = str(json_body or '')

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class FakeGraph:
    """Graph minimo: metadados, conteudo, motor Excel e PUTs de upload."""

    conteudo = b''
    workbook = FakeResponse(json_body={'value': [{'name': 'Demandas'}]})
    workbook_apos_reparo = None
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.__class__.calls.append(('GET', url))
        if url.endswith('/workbook/worksheets'):
            reparado = any(metodo == 'PUT' and rota.endswith('/content') for metodo, rota in self.__class__.calls)
            if reparado and self.__class__.workbook_apos_reparo is not None:
                return self.__class__.workbook_apos_reparo
            return self.__class__.workbook
        if url.endswith('/content'):
            return FakeResponse(content=self.__class__.conteudo)
        return FakeResponse(
            json_body={
                'id': ITEM,
                'name': 'WSJF.xlsx',
                'webUrl': 'https://contoso.sharepoint.com/WSJF.xlsx',
                'lastModifiedDateTime': '2026-09-03T10:00:00Z',
                'parentReference': {'id': 'pasta-raiz'},
            }
        )

    async def put(self, url, **kwargs):
        self.__class__.calls.append(('PUT', url))
        self.__class__.enviado = kwargs.get('content')
        return FakeResponse(json_body={'id': ITEM, 'name': 'WSJF.xlsx'})


def _preparar(monkeypatch, conteudo: bytes, workbook=None, workbook_apos_reparo=None):
    FakeGraph.conteudo = conteudo
    FakeGraph.workbook = workbook or FakeResponse(json_body={'value': [{'name': 'Demandas'}]})
    FakeGraph.workbook_apos_reparo = workbook_apos_reparo
    FakeGraph.calls = []
    monkeypatch.setattr(servico.httpx, 'AsyncClient', FakeGraph)
    monkeypatch.setattr(servico, '_token', _token_falso)


async def _token_falso(scope: str) -> str:
    return 'graph-token-teste'


def _template() -> bytes:
    return base64.b64decode(TEMPLATE.read_text(encoding='ascii'))


def _corrompido() -> bytes:
    """Pacote sem docProps: o defeito que o Graph recusa e o Excel tolera."""
    origem = _template()
    saida = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(origem)) as entrada, zipfile.ZipFile(saida, 'w') as destino:
        for nome in entrada.namelist():
            if not nome.startswith('docProps/'):
                destino.writestr(nome, entrada.read(nome))
    return saida.getvalue()


def _recusa_do_graph():
    return FakeResponse(
        status_code=400,
        json_body={'error': {'code': 'unsupportedWorkbook', 'message': 'FileCorruptTryRepair'}},
    )


def test_diagnostico_aprova_o_template_canonico(auth_override, monkeypatch):
    _preparar(monkeypatch, _template())

    resposta = client.post(f'{BASE}/excel/diagnostico', json={'excel_drive': DRIVE, 'excel_file': ITEM})
    dados = resposta.json()['data']

    assert resposta.status_code == 200
    assert dados['compativel'] is True
    assert dados['precisa_reparo'] is False
    assert dados['erros_pacote'] == []
    assert dados['arquivo']['nome'] == 'WSJF.xlsx'


def test_diagnostico_aponta_reparo_quando_o_graph_recusa_o_arquivo(auth_override, monkeypatch):
    _preparar(monkeypatch, _corrompido(), workbook=_recusa_do_graph())

    dados = client.post(f'{BASE}/excel/diagnostico', json={'excel_drive': DRIVE, 'excel_file': ITEM}).json()['data']

    assert dados['compativel'] is False
    assert dados['precisa_reparo'] is True
    assert dados['graph_recusou_arquivo'] is True
    assert any('docProps' in erro for erro in dados['erros_pacote'])


def test_diagnostico_nao_pede_reparo_quando_a_falha_e_de_permissao(auth_override, monkeypatch):
    negado = FakeResponse(status_code=403, json_body={'error': {'code': 'accessDenied'}})
    _preparar(monkeypatch, _template(), workbook=negado)

    dados = client.post(f'{BASE}/excel/diagnostico', json={'excel_drive': DRIVE, 'excel_file': ITEM}).json()['data']

    assert dados['compativel'] is False
    assert dados['precisa_reparo'] is False
    assert 'accessDenied' in dados['graph_erro']


def test_diagnostico_recusa_identificador_com_travessia_de_caminho(auth_override, monkeypatch):
    _preparar(monkeypatch, _template())

    resposta = client.post(
        f'{BASE}/excel/diagnostico', json={'excel_drive': DRIVE, 'excel_file': '../../me/drive'}
    )

    assert resposta.status_code == 409
    assert FakeGraph.calls == []


def test_diagnostico_recusa_segmento_de_caminho_que_o_httpx_normalizaria(auth_override, monkeypatch):
    """`..` passa por qualquer allowlist que aceite ponto, mas o httpx o resolve:
    /v1.0/drives/../items/{id} vira /v1.0/items/{id}, outro endpoint do Graph."""
    _preparar(monkeypatch, _template())

    for identificador in ('..', '.', '.oculto'):
        resposta = client.post(
            f'{BASE}/excel/diagnostico', json={'excel_drive': identificador, 'excel_file': ITEM}
        )
        # 409 pelo validador; 422 quando o Pydantic ja barra pelo tamanho minimo.
        assert resposta.status_code in (409, 422), identificador

    assert FakeGraph.calls == []


def test_reparo_guarda_copia_grava_no_mesmo_item_e_reverifica(auth_override, monkeypatch):
    _preparar(
        monkeypatch,
        _corrompido(),
        workbook=_recusa_do_graph(),
        workbook_apos_reparo=FakeResponse(json_body={'value': [{'name': 'Demandas'}]}),
    )

    dados = client.post(
        f'{BASE}/excel/reparar', json={'excel_drive': DRIVE, 'excel_file': ITEM, 'confirmar': True}
    ).json()['data']

    assert dados['reparado'] is True
    assert dados['copia_de_seguranca'].startswith('WSJF.incompativel-')
    puts = [url for metodo, url in FakeGraph.calls if metodo == 'PUT']
    assert len(puts) == 2
    assert f":/{dados['copia_de_seguranca']}:/content" in puts[0]
    assert puts[1].endswith(f'/items/{ITEM}/content')


def test_reparo_exige_confirmacao_explicita(auth_override, monkeypatch):
    _preparar(monkeypatch, _corrompido(), workbook=_recusa_do_graph())

    resposta = client.post(f'{BASE}/excel/reparar', json={'excel_drive': DRIVE, 'excel_file': ITEM})

    assert resposta.status_code == 409
    assert FakeGraph.calls == []


def _payload_deploy():
    return {
        'environment_id': 'env-dev-001',
        'environment_url': 'https://org-dev.crm2.dynamics.com',
        'group_id': 'group-dev-001',
        'plan_id': 'plan-dev-001',
        'excel_source': 'groups/group-dev-001',
        'excel_drive': DRIVE,
        'excel_file': ITEM,
        'planner_connection_id': 'planner-connection-dev',
        'excel_connection_id': 'excel-connection-dev',
        'target_environment': 'dev',
    }


def test_deploy_recusa_instalar_sobre_planilha_que_o_graph_rejeita(auth_override, monkeypatch):
    _preparar(monkeypatch, _corrompido(), workbook=_recusa_do_graph())
    monkeypatch.setattr('app.api.wsjf_planner_excel.validar_destino_assistente', _destino_ok)
    monkeypatch.setattr('app.api.wsjf_planner_excel.despachar', _despachar_proibido)

    resposta = client.post(f'{BASE}/deploy', json=_payload_deploy())

    assert resposta.status_code == 409
    assert 'Regenerar WSJF.xlsx' in resposta.json()['detail']


def test_deploy_segue_quando_o_diagnostico_falha_por_motivo_alheio_ao_arquivo(auth_override, monkeypatch):
    async def _diagnostico_indisponivel(drive, item):
        raise RuntimeError('Graph indisponivel')

    monkeypatch.setattr('app.api.wsjf_planner_excel.diagnosticar_workbook', _diagnostico_indisponivel)
    monkeypatch.setattr('app.api.wsjf_planner_excel.validar_destino_assistente', _destino_ok)
    monkeypatch.setattr('app.api.wsjf_planner_excel.despachar', _despachar_ok)

    resposta = client.post(f'{BASE}/deploy', json=_payload_deploy())

    assert resposta.status_code == 200
    assert resposta.json()['data']['status'] == 'implantado'


async def _destino_ok(environment_id, environment_url):
    return None


async def _despachar_ok(payload, user_token=None):
    return {'dispatched': True, 'status': 'implantado', 'correlation_id': 'corr-1'}


async def _despachar_proibido(payload, user_token=None):
    raise AssertionError('despachar nao pode ser chamado com planilha invalida')
