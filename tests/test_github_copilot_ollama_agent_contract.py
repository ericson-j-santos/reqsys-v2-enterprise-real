from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_is_user_invocable_and_uses_only_governed_mcp_endpoint() -> None:
    raw = (ROOT / ".github" / "agents" / "ollama.agent.md").read_text(encoding="utf-8")
    assert "name: Ollama" in raw
    assert "target: github-copilot" in raw
    assert "user-invocable: true" in raw
    assert "disable-model-invocation: true" in raw
    assert "ollama-reqsys/ollama_analyze" in raw
    assert "${{ vars.COPILOT_MCP_OLLAMA_URL }}" in raw
    assert "${{ secrets.COPILOT_MCP_OLLAMA_TOKEN }}" in raw
    assert "http://127.0.0.1:11434" not in raw
    assert "localhost:11434" not in raw


def test_server_requires_bearer_and_is_read_only_loopback_service() -> None:
    raw = (
        ROOT / "services" / "ollama-mcp-bridge" / "server.py"
    ).read_text(encoding="utf-8")
    assert 'os.getenv("OLLAMA_MCP_BEARER_TOKEN"' in raw
    assert "hmac.compare_digest" in raw
    assert "read_only_hint=True" in raw
    assert "destructive_hint=False" in raw
    assert 'host="127.0.0.1"' in raw
    assert "port=8010" in raw
    assert "11434" not in raw


def test_bridge_dependency_is_version_bounded() -> None:
    raw = (
        ROOT / "services" / "ollama-mcp-bridge" / "requirements.txt"
    ).read_text(encoding="utf-8")
    assert "mcp>=2.0,<3.0" in raw
