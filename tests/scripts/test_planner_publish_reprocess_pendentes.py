import importlib.util
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / 'scripts' / 'planner_publish_reprocess_pendentes.py'
spec = importlib.util.spec_from_file_location('planner_reprocess', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = json.dumps(body).encode('utf-8')

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code, body):
    exc = HTTPError('url', code, 'erro', {}, None)
    exc.read = lambda: json.dumps(body).encode('utf-8')
    return exc


def test_reprocessa_publicados_e_recusados(monkeypatch):
    pendentes = {
        'success': True,
        'data': {'items': [
            {'attempt_id': 1, 'status': 'falhou_integracao'},
            {'attempt_id': 2, 'status': 'falhou_integracao'},
            {'attempt_id': 3, 'status': 'falhou_integracao'},
        ]},
    }
    respostas = {
        1: (200, {'success': True, 'data': {'status': 'publicado'}}),
        2: (200, {'success': True, 'data': {'status': 'falhou_integracao'}}),
        3: (409, {'detail': 'já publicado'}),
    }

    def fake_urlopen(req, timeout=20):
        if req.get_method() == 'GET':
            return _FakeResponse(200, pendentes)
        attempt_id = int(req.full_url.split('/publish/')[1].split('/')[0])
        status, body = respostas[attempt_id]
        if status != 200:
            raise _http_error(status, body)
        return _FakeResponse(status, body)

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    resultados_capturados = []
    original_reprocessar = module.reprocessar

    def _spy(*args, **kwargs):
        out = original_reprocessar(*args, **kwargs)
        resultados_capturados.append(out)
        return out

    monkeypatch.setattr(module, 'reprocessar', _spy)

    import argparse
    args = argparse.Namespace(
        base_url='https://example.test', service_token='tok', lote_max=10,
        timeout=5, evidence_file=None, strict=False,
    )
    pendentes_listados = module.listar_pendentes(args.base_url, args.service_token, args.lote_max, args.timeout)
    assert len(pendentes_listados) == 3

    desfechos = []
    for item in pendentes_listados:
        status_http, resposta = module.reprocessar(args.base_url, args.service_token, item['attempt_id'], args.timeout)
        desfechos.append((status_http, resposta.get('data', {}).get('status')))

    assert desfechos[0] == (200, 'publicado')
    assert desfechos[1] == (200, 'falhou_integracao')
    assert desfechos[2][0] == 409


def test_listar_pendentes_erro_http_levanta_system_exit(monkeypatch):
    def fake_urlopen(req, timeout=20):
        raise _http_error(401, {'detail': 'Token de serviço inválido, expirado ou revogado'})

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    with pytest.raises(SystemExit):
        module.listar_pendentes('https://example.test', 'tok-invalido', 10, 5)


def test_main_fluxo_completo_grava_evidencia(monkeypatch, tmp_path, capsys):
    pendentes = {'success': True, 'data': {'items': [{'attempt_id': 42, 'status': 'falhou_integracao'}]}}
    reprocesso = {'success': True, 'data': {'status': 'publicado'}}

    def fake_urlopen(req, timeout=20):
        if req.get_method() == 'GET':
            return _FakeResponse(200, pendentes)
        return _FakeResponse(200, reprocesso)

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)

    evidence_file = tmp_path / 'resumo.json'
    monkeypatch.setattr(sys, 'argv', [
        'planner_publish_reprocess_pendentes.py',
        '--base-url', 'https://example.test',
        '--service-token', 'tok',
        '--evidence-file', str(evidence_file),
    ])

    module.main()

    assert evidence_file.exists()
    resumo = json.loads(evidence_file.read_text(encoding='utf-8'))
    assert resumo['total_pendentes_encontrados'] == 1
    assert resumo['resultados'][0]['desfecho'] == 'publicado'
    assert resumo['total_inesperados'] == 0
