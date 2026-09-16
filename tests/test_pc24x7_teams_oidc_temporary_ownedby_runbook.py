from pathlib import Path


RUNBOOK = Path('docs/runbooks/pc24x7-teams-oidc-temporary-ownedby.md')


def test_runbook_proibe_escalada_automatica_e_limita_dev() -> None:
    text = RUNBOOK.read_text(encoding='utf-8')
    assert 'a automação nunca promove para `Application.ReadWrite.All`' in text
    assert 'MUTATOR_NOT_OWNER' in text
    assert 'TEST/HML/PROD não são alterados' in text
