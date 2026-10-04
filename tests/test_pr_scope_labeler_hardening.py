from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pr_scope_labeler_permanece_read_only_e_sem_pull_request_target() -> None:
    workflow = (ROOT / ".github/workflows/pr-scope-labeler.yml").read_text(encoding="utf-8")

    assert "pull_request_target" not in workflow
    assert "pull_request:" in workflow
    assert "issues: write" not in workflow
    assert "Modo', 'read-only; fail-safe; sem mutacao de labels'" in workflow
    assert "github.rest.issues.addLabels" not in workflow
    assert "github.rest.issues.removeLabel" not in workflow


def test_coderabbit_nao_e_reintroduzido_como_dependencia_operacional() -> None:
    config = (ROOT / ".coderabbit.yaml").read_text(encoding="utf-8")

    assert "CodeRabbit desativado operacionalmente" in config
    assert "PR Quality Review" in config
    assert "enable_free_tier:" not in config
    assert "auto_review:" not in config
