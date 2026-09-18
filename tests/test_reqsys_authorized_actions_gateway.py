from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_gateway_restringe_issue_ator_e_comandos_exatos() -> None:
    content = _workflow()

    assert "github.event.issue.number == 1705" in content
    assert "github.event.comment.user.login == 'ericson-j-santos'" in content
    assert "github.event.comment.body == '/reqsys run bootstrap-wsjf-m365-dev'" in content
    assert "github.event.comment.body == '/reqsys run runtime-e2e-dev'" in content
    assert "github.event.comment.body == '/reqsys run pending-agent-pr-permission-watch'" in content


def test_gateway_usa_allowlist_estatica_sem_workflow_arbitrario() -> None:
    content = _workflow()

    assert "target='bootstrap-wsjf-m365-dev.yml'" in content
    assert "target='runtime-e2e-continuous.yml'" in content
    assert "target='pending-development-agent-pr-permission-watch.yml'" in content
    assert (
        "bootstrap-wsjf-m365-dev.yml|runtime-e2e-continuous.yml|"
        "pending-development-agent-pr-permission-watch.yml"
    ) in content
    assert 'gh workflow run "$TARGET_WORKFLOW"' in content
    assert "eval " not in content


def test_gateway_fixa_main_e_permissoes_minimas() -> None:
    content = _workflow()

    permissions = content.split("permissions:\n", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "actions: write" in permissions
    assert "contents: read" in permissions
    assert "contents: write" not in permissions
    assert "id-token: write" not in permissions
    assert "--ref main" in content
    assert "target_ref': 'main'" in content


def test_gateway_publica_evidencia_sanitizada() -> None:
    content = _workflow()

    assert "authorized-action-dispatch.json" in content
    assert "'secrets_read': False" in content
    assert "'production_touched': False" in content
    assert "target_run_url" in content
    assert "target_sha" in content
