from pathlib import Path


ADR = Path("docs/adr/ADR-046-pc24x7-substituicao-flyio.md")
RUNBOOK = Path("docs/runbooks/pc24x7-piloto-dev.md")
BACKUP_SCRIPT = Path("scripts/pc24x7_backup_restic.sh")


def test_pc24x7_pilot_artifacts_exist() -> None:
    assert ADR.is_file()
    assert RUNBOOK.is_file()
    assert BACKUP_SCRIPT.is_file()


def test_pc24x7_pilot_does_not_promote_hml_or_prod_automatically() -> None:
    adr = ADR.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "piloto restrito a dev" in adr
    assert "HML e PROD não são promovidos por este runbook" in runbook
    assert "Não copiar automaticamente DEV para HML/PROD" in runbook
    assert "Quick Tunnel" in runbook


def test_pc24x7_cost_comparison_is_documented() -> None:
    adr = ADR.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "Comparação de custo inicial" in adr
    assert "Domínio" in adr
    assert "Energia" in adr
    assert "Administração" in adr
    assert "Sem domínio próprio, manter Quick Tunnel apenas para DEV" in runbook


def test_pc24x7_backup_placeholder_has_no_legacy_provider_commands() -> None:
    script = BACKUP_SCRIPT.read_text(encoding="utf-8")

    assert "flyctl" not in script
    assert "FLY_API_TOKEN" not in script
    assert "*.fly.dev" not in script
