from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "desktop-runtime-runner-bridge.yml"
REQUIREMENTS = ROOT / ".sdd" / "specs" / "desktop-runtime-runner-bridge.requirements.md"


def test_bridge_is_governed_and_fail_closed():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    requirements = REQUIREMENTS.read_text(encoding="utf-8")

    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in workflow
    assert "RUNTIME_SHA: 05f9c63253f7da1eb73d88db5494a98471f0df2e" in workflow
    assert "RULES_SHA: ac2297988651f41ab03469808e41f83496e9c58f" in workflow
    assert "session_launcher.py" in workflow
    assert "SESSION_LAUNCH_OK" in workflow
    assert "state_validated" in workflow
    assert "command_gateway.py" in workflow
    assert '"--risk", "2"' in workflow
    assert "activate_desktop_runtime_runner.py" in workflow
    assert "ACTIVATE-DESKTOP-RUNTIME-RUNNER" in workflow
    assert "--non-interactive-auth" in workflow
    assert "GH_PAT_ACTIONS" not in workflow
    assert "cancel-in-progress: true" in workflow
    assert "WORKER_POOL_RUNTIME_SMOKE_PASSED" in requirements
    assert "WORKER_POOL_SMOKE_PASSED" in requirements


def test_bridge_resolves_main_when_legacy_runner_picks_up():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Resolve current ReqSys main anchor" in workflow
    assert "github.rest.repos.getBranch" in workflow
    assert "branch: 'main'" in workflow
    assert '"--expected-head", $anchorSha' in workflow
    assert '"--sync-ref", "origin/main"' in workflow
