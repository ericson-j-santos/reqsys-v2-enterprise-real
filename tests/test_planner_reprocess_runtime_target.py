"""O agendamento deve recusar alvos legados antes de enviar o service token."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/planner-publish-reprocess-scheduled.yml'


def resolver_source():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))
    step = next(step for step in workflow['jobs']['reprocessar']['steps'] if step.get('id') == 'resolver')
    return step['run'].split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]


@pytest.mark.parametrize('url', [
    '', 'https://reqsys-api-dev.fly.dev', 'http://pc24x7.example.test/api',
    'https://user:password@pc24x7.example.test/api',
    'https://pc24x7.example.test/api?token=example',
])
def test_recusa_alvo_invalido_sem_publicar_output(url, tmp_path):
    output = tmp_path / 'output'
    env = {**os.environ, 'REQSYS_API_BASE_URL': url, 'GITHUB_OUTPUT': str(output)}
    result = subprocess.run([sys.executable, '-c', resolver_source()], env=env, capture_output=True)
    assert result.returncode != 0
    assert not output.exists()


def test_preserva_prefixo_api_pc24x7(tmp_path):
    output = tmp_path / 'output'
    env = {**os.environ, 'REQSYS_API_BASE_URL': 'https://pc24x7.example.test/api/', 'GITHUB_OUTPUT': str(output)}
    result = subprocess.run([sys.executable, '-c', resolver_source()], env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert output.read_text() == 'base_url=https://pc24x7.example.test/api\n'
