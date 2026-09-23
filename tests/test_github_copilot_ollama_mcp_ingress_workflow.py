from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "github-copilot-ollama-mcp-ingress-dev.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def test_workflow_is_dev_only_fixed_desktop_and_sanitized() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "pc24x7_ollama_mcp_funnel.py" in raw
    assert "--apply" in raw
    assert "--source-sha" in raw
    assert "github.sha" in raw
    assert "OLLAMA_MCP_BEARER_TOKEN" not in raw
    assert "11434 público: não" in raw
    assert "8008 público: não" in raw
    assert "Produção tocada: não" in raw


def test_workflow_is_explicitly_approved_for_self_hosted() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/github-copilot-ollama-mcp-ingress-dev.yml" in policy["approved_workflows"]


def test_authorized_gateway_has_exact_inputless_route_and_pickup_guard() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    command = "/reqsys run github-copilot-ollama-mcp-ingress-dev"
    workflow = "github-copilot-ollama-mcp-ingress-dev.yml"
    assert f"github.event.comment.body == '{command}'" in raw
    assert f"'{command}')" in raw
    assert f"target='{workflow}'" in raw
    assert f"steps.route.outputs.target == '{workflow}'" in raw
    assert "SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY" in raw
    assert "-f target=" not in raw
