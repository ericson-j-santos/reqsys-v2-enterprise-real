from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_factory_fabric_fic_preflight.py"
WORKFLOW = ROOT / ".github" / "workflows" / "report-factory-fabric-fic-preflight.yml"


def test_script_is_read_only_and_never_embeds_secret() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'method="GET"' in text
    assert 'method="POST"' not in text
    assert 'method="PATCH"' not in text
    assert 'method="DELETE"' not in text
    assert "client_secret" not in text.casefold()
    assert "password" not in text.casefold()
    assert '"mutation_performed": False' in text
    assert '"secret_value_exposed": False' in text
    assert '"identifiers_exposed": False' in text


def test_workflow_runs_only_readonly_probe_on_noteri() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "self-hosted, Windows, X64, noteri, reqsys-dev" in text
    assert "report_factory_fabric_fic_preflight.py" in text
    assert "workflow_dispatch:" in text
    assert "id-token: write" not in text
    assert "client-secret" not in text
    assert "az login" not in text
    assert "fic_ready=" in text
    assert "unexpected_mutation" in text
