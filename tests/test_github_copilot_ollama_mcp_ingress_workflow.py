from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "codex-ollama-e2e-dev.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def test_canonical_workflow_reuses_dev_runner_with_closed_mcp_mode() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert 'default: "codex-e2e"' in raw
    assert "- codex-e2e" in raw
    assert "- mcp-ingress" in raw
    assert "if: inputs.mode == 'mcp-ingress'" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "actions/setup-python@" not in raw
    assert raw.count("Get-Command python -CommandType Application -ErrorAction Stop") == 2
    assert 'REQSYS_PYTHON=$pythonExe' in raw
    assert "services/ollama-mcp-bridge/requirements.txt" in raw
    assert '& "$env:REQSYS_PYTHON" scripts/codex_pc24x7_supervisor.py install' in raw
    assert '--source-root "${{ github.workspace }}"' in raw
    assert '--source-sha "${{ github.sha }}"' in raw
    assert '--python-executable "$env:REQSYS_PYTHON"' in raw
    assert "CODEX_PC24X7_SUPERVISOR_RECONCILE_FAILED" in raw
    assert '& "$env:REQSYS_PYTHON" scripts/pc24x7_ollama_mcp_funnel.py' in raw
    assert "pc24x7_ollama_mcp_funnel.py" in raw
    assert "--apply" in raw
    assert "--source-sha" in raw
    assert "github.sha" in raw
    assert "OLLAMA_MCP_BEARER_TOKEN" not in raw
    assert "11434 público: não" in raw
    assert "8008 público: não" in raw
    assert "Produção tocada: não" in raw


def test_existing_self_hosted_policy_is_preserved_without_new_workflow() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/codex-ollama-e2e-dev.yml" in policy["approved_workflows"]
    assert ".github/workflows/branch-protection-audit.yml" in policy["approved_workflows"]
    assert ".github/workflows/github-copilot-ollama-mcp-ingress-dev.yml" not in policy["approved_workflows"]


def test_authorized_gateway_maps_exact_commands_to_closed_modes() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run github-copilot-ollama-mcp-ingress-dev'" in raw
    assert "'/reqsys run github-copilot-ollama-mcp-ingress-dev')" in raw
    assert "target='codex-ollama-e2e-dev.yml'" in raw
    assert "mode='mcp-ingress'" in raw
    assert "mode='codex-e2e'" in raw
    assert "codex-e2e|mcp-ingress" in raw
    assert '-f mode="$TARGET_MODE"' in raw
    assert "SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY" in raw
    assert "-f target=" not in raw


def test_workflow_surface_is_reused_not_expanded() -> None:
    assert not (ROOT / ".github" / "workflows" / "github-copilot-ollama-mcp-ingress-dev.yml").exists()
