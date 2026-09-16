from pathlib import Path


RUNBOOK = Path('docs/runbooks/pc24x7-teams-oidc-temporary-ownedby.md')


def test_runbook_proibe_promocao_automatica_para_all() -> None:
    text = RUNBOOK.read_text(encoding='utf-8')
    assert 'A automação nunca promove para `Application.ReadWrite.All`' in text
    assert 'Somente DEV' in text
    assert 'TEST/HML/PROD não são alterados' in text
