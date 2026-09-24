import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/teams-bot-dev-identity-bootstrap.yml"
GATEWAY = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
CONFIG = ROOT / "scripts/configure_teams_bot_dev_identity_risk3.py"
RUNNER = ROOT / "scripts/run_teams_bot_dev_identity_bootstrap_local.py"

config_spec = importlib.util.spec_from_file_location("teams_bot_identity_risk3", CONFIG)
assert config_spec and config_spec.loader
config_module = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config_module)


def test_risk3_action_is_exact_dev_only_and_secret_free():
    assert config_module.ACTION_ID == "reqsys.teams-bot-dev-identity-bootstrap.dev"
    assert config_module.SCOPE == "repo://ericson-j-santos/reqsys-v2-enterprise-real/environment/dev/teams-bot-identity"
    assert config_module.COMMAND == [
        "python",
        "scripts/run_teams_bot_dev_identity_bootstrap_local.py",
        "--output",
        "artifacts/teams-bot-dev-identity-bootstrap/evidence.json",
    ]
    raw = CONFIG.read_text(encoding="utf-8")
    assert "--tenant-id" not in raw
    assert "--secret" not in raw
    assert "ttl_minutes > 60" in raw


def test_workflow_uses_session_launcher_owner_risk3_and_exact_noteri():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert 'if ($env:COMPUTERNAME -ne "NOTERI")' in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert '"--sync-ref", "origin/main"' in raw
    assert "owner_risk3_gateway.py" in raw
    assert "ENABLE-TEAMS-BOT-DEV-IDENTITY-BOOTSTRAP-ONCE" in raw
    assert "DISABLE-TEAMS-BOT-DEV-IDENTITY-BOOTSTRAP-ONCE" in raw
    assert "CCP_AZURE_TENANT_ID: ${{ vars.CCP_AZURE_TENANT_ID }}" in raw


def test_runner_is_idempotent_and_reads_back_without_secret_output():
    raw = RUNNER.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "NOTERI"' in raw
    assert 'CONFIRMATION = "CRIAR-IDENTIDADE-TEAMS-BOT-DEV"' in raw
    assert "dry_run=True" in raw
    assert "dry_run=False" in raw
    assert "independent_readback_not_complete" in raw
    assert '"secret_value_exposed": False' in raw
    assert '"production_touched": False' in raw
    assert "shell=False" in raw


def test_authorized_gateway_exposes_only_literal_command():
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "/reqsys run teams-bot-dev-identity-bootstrap" in raw
    assert "teams-bot-dev-identity-bootstrap.yml" in raw
    assert "github.event.issue.number == 1705" in raw
    assert "github.event.comment.user.login == 'ericson-j-santos'" in raw
