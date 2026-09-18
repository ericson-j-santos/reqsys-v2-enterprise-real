from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/planner-teams-notify-dev-acceptance.yml"


def test_acceptance_uses_pc24x7_runtime_fail_closed() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "API_URL: ${{ vars.PC24X7_DEV_BASE_URL }}" in source
    assert "https://reqsys-api-dev.fly.dev" not in source
    assert "PC24X7_DEV_BASE_URL não configurada" in source
    assert "PC24X7_DEV_BASE_URL deve usar HTTPS" in source
    assert "Planner Teams DEV Acceptance não pode usar Fly.io" in source
    assert '${API_URL%/}/api/runtime/health' in source
