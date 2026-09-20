from pathlib import Path

WORKFLOW = Path(".github/workflows/figma-github-e2e-dev.yml")
SCRIPT = Path("scripts/figma_github_dev_e2e.py")
GATEWAY = Path(".github/workflows/reqsys-authorized-actions-gateway.yml")
POLICY = Path(".github/self-hosted-runner-policy.json")


def test_workflow_is_fixed_to_pc24x7_dev() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "schedule:" not in raw
    assert "pull_request:" not in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert '--expected-sha "${{ github.sha }}"' in raw
    assert "production_touched" not in raw or "Produção tocada: não" in raw


def test_script_uses_fixed_targets_and_replay_guard() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "DESKTOP-PDQK954"' in raw
    assert 'CONTAINER = "wt-pc24x7-piloto-api-1"' in raw
    assert 'FIGMA_FILE_KEY = "1iA8PiHX7qMnYHBDTdt0fY"' in raw
    assert 'FIGMA_NODE_ID = "1:44"' in raw
    assert 'GITHUB_REPO = "ericson-j-santos/reqsys-v2-enterprise-real"' in raw
    assert '"mode": "bidirectional"' in raw
    assert "replay_not_idempotent" in raw
    assert '"production_touched": False' in raw
    assert "FIGMA_ACCESS_TOKEN" in raw
    assert "GITHUB_TOKEN" in raw


def test_authorized_gateway_has_exact_figma_route() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.issue.number == 1705" in raw
    assert "github.event.comment.user.login == 'ericson-j-santos'" in raw
    assert "github.event.comment.body == '/reqsys run figma-github-e2e-dev'" in raw
    assert "target='figma-github-e2e-dev.yml'" in raw


def test_self_hosted_policy_explicitly_allowlists_figma_e2e() -> None:
    import json

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["self_hosted_allowed"] is True
    assert ".github/workflows/figma-github-e2e-dev.yml" in policy["approved_workflows"]
    assert policy["required_adr"] == "docs/adr/ADR-046-pc24x7-substituicao-flyio.md"
