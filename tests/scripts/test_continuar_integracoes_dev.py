import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('continuar_dev', ROOT / 'scripts/continuar_integracoes_dev.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_locator_indisponivel_nao_reprocessa_nem_expoe_segundo(monkeypatch):
    monkeypatch.setenv('PLANNER_PUBLISH_SERVICE_TOKEN', 'segredo-local-de-teste')
    monkeypatch.setattr(module, 'resolver_dev', lambda: (_ for _ in ()).throw(RuntimeError('locator_dev_indisponivel')))
    report = module.preflight()
    module.executar_planner(report)
    assert report['status'] == 'BLOCKED_EXTERNAL'
    assert report['planner_reprocess_executed'] is False
    assert 'segredo-local-de-teste' not in str(report)


@pytest.mark.parametrize('token,sha,expected', [
    ('', 'a' * 40, 'BLOCKED_EXTERNAL'),
    ('test-only-token', '', 'BLOCKED_EXTERNAL'),
    ('test-only-token', 'a' * 40, 'ready_for_planner_reprocess'),
])
def test_saude_e_sha_nao_substituem_token(monkeypatch, token, sha, expected):
    monkeypatch.setenv('PLANNER_PUBLISH_SERVICE_TOKEN', token)
    monkeypatch.setattr(module, 'resolver_dev', lambda: 'https://dev.example.test/api')
    monkeypatch.setattr(module, 'ler_runtime', lambda *_: {'data': {'status': 'ok', 'build_sha': sha}})
    report = module.preflight()
    assert report['status'] == expected
    assert report['redmine_live_validation'] == 'pending'


def test_locator_canonico_recebe_contexto_sem_github_output(monkeypatch):
    monkeypatch.setenv('GITHUB_OUTPUT', '/unused-output')
    def fake_run(args, **kwargs):
        assert args[1].endswith('resolve_pc24x7_dev_locator.mjs')
        assert 'GITHUB_OUTPUT' not in kwargs['env']
        return SimpleNamespace(returncode=0, stdout='{"signature_verified":true,"environment":"dev","selected_url":"https://dev.trycloudflare.com"}')
    monkeypatch.setattr(module.subprocess, 'run', fake_run)
    assert module.resolver_dev() == 'https://dev.trycloudflare.com/api'


def test_reprocessamento_usa_implementacao_existente(monkeypatch):
    monkeypatch.setenv('PLANNER_PUBLISH_SERVICE_TOKEN', 'test-only-token')
    calls = []
    monkeypatch.setitem(sys.modules, 'planner_publish_reprocess_pendentes', SimpleNamespace(main=lambda: calls.append(sys.argv[:])))
    report = {'status': 'ready_for_planner_reprocess', 'api_base_url': 'https://dev.example.test/api', 'blockers': [], 'expected_sha_verified': True}
    module.executar_planner(report)
    assert report['planner_reprocess_executed'] is True
    assert '--strict' in calls[0]
    assert report['status'] == 'planner_reprocess_completed'


def test_sha_divergente_impede_reprocessamento(monkeypatch):
    monkeypatch.setenv('PLANNER_PUBLISH_SERVICE_TOKEN', 'test-only-token')
    monkeypatch.setattr(module, 'resolver_dev', lambda: 'https://dev.example.test/api')
    monkeypatch.setattr(module, 'ler_runtime', lambda *_: {'data': {'status': 'ok', 'build_sha': 'a' * 40}})
    report = module.preflight('b' * 40)
    module.executar_planner(report)
    assert 'runtime_sha_divergente' in report['blockers']
    assert report['planner_reprocess_executed'] is False
