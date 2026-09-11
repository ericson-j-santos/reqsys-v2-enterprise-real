from pathlib import Path


ADR = Path("docs/adr/ADR-046-pc24x7-substituicao-flyio.md")
RUNBOOK = Path("docs/runbooks/pc24x7-piloto-dev.md")
BACKUP_SCRIPT = Path("scripts/pc24x7_backup_restic.sh")


def test_pc24x7_pilot_artifacts_exist() -> None:
    assert ADR.is_file()
    assert RUNBOOK.is_file()
    assert BACKUP_SCRIPT.is_file()


def test_pc24x7_pilot_stays_dev_only_until_evidence() -> None:
    adr = ADR.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "piloto restrito a dev" in adr
    assert "hml/prod seguem no Fly.io" in adr
    assert "hml e prod continuam no Fly.io" in runbook
    assert "Quick Tunnel" in runbook


def test_pc24x7_cost_comparison_is_documented() -> None:
    adr = ADR.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "Comparação de custo inicial" in adr
    assert "Domínio" in adr
    assert "Energia" in adr
    assert "Administração" in adr
    assert "Acompanhamento de custo sem gasto novo" in runbook


def test_pc24x7_backup_script_uses_restic_and_retention() -> None:
    script = BACKUP_SCRIPT.read_text(encoding="utf-8")

    assert "RESTIC_REPOSITORY" in script
    assert "pg_dump" in script
    assert "restic backup" in script
    assert "restic forget" in script
    assert "restic check" in script
