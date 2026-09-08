import json
from pathlib import Path


MANIFEST_PATH = Path('infra/teams-app/manifest.json')


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))


def test_manifest_habilita_bot_conversacional_para_central_de_ia():
    manifest = _manifest()
    bots = manifest.get('bots') or []

    assert len(bots) == 1
    bot = bots[0]
    assert bot['botId'] == '${{TEAMS_BOT_APP_ID}}'
    assert 'personal' in bot['scopes']
    assert bot['isNotificationOnly'] is False


def test_manifest_nao_embute_credencial_do_bot():
    texto = MANIFEST_PATH.read_text(encoding='utf-8')

    assert 'TEAMS_BOT_SECRET' not in texto
    assert '${{TEAMS_BOT_APP_ID}}' in texto


def test_manifest_versiona_mudanca_conversacional():
    manifest = _manifest()

    assert manifest['version'] == '1.1.0'
