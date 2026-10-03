import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE_SURFACES = (
    'frontend/src/constants/ambientesOperacionais.js',
    'frontend/src/views/ArquiteturaView.vue',
    'backend/app/core/config.py',
    'backend/app/services/github_launchpad.py',
    'infra/teams-app/manifest.json',
    'scripts/build_teams_app_package.py',
    'tools/codex-local-online/index.html',
)
RETIRED_URL = re.compile(r'https?://[^\s"\'<>]*fly\.(?:dev|io)', re.IGNORECASE)


@pytest.mark.parametrize('relative_path', EXECUTABLE_SURFACES)
def test_superficie_nao_expoe_url_executavel_do_provedor_retirado(relative_path: str) -> None:
    source = (ROOT / relative_path).read_text(encoding='utf-8')

    assert not RETIRED_URL.search(source), relative_path
    assert 'flyctl' not in source.lower(), relative_path


def test_codex_online_exige_endpoint_remoto_explicito() -> None:
    source = (ROOT / 'tools/codex-local-online/index.html').read_text(encoding='utf-8')

    assert "return ''" in source
    assert 'Informe explicitamente o endpoint governado' in source
    assert "const dominiosRetirados = ['fly.dev', 'fly.io']" in source
    assert 'if (!endpointPermitido(endpoint))' in source
