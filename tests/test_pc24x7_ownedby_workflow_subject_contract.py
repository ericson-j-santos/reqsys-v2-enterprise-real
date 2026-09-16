from pathlib import Path


def test_workflow_nao_declara_environment_github() -> None:
    text = Path('.github/workflows/pc24x7-teams-oidc-environment-bootstrap.yml').read_text(encoding='utf-8')
    assert '\n    environment:' not in text
    assert '--ref main' not in text  # dispatch é feito pelo orquestrador; workflow apenas executa o ref recebido
