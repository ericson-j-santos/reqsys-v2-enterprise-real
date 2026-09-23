from __future__ import annotations

import hmac
import os
from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from bridge import BridgeError, analyze

mcp = MCPServer(
    "ReqSys Ollama MCP Bridge",
    instructions=(
        "Use ollama_analyze for substantive code/chat/RAG analysis. "
        "The tool is read-only and routes only through the governed loopback Ollama gateway."
    ),
)


def _authorize(ctx: Context) -> None:
    expected = os.getenv("OLLAMA_MCP_BEARER_TOKEN", "").strip()
    if not expected:
        raise BridgeError("mcp_bearer_token_not_configured")
    headers = {str(key).lower(): str(value) for key, value in (ctx.headers or {}).items()}
    authorization = headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise BridgeError("mcp_unauthorized")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise BridgeError("mcp_unauthorized")


@mcp.tool(
    name="ollama_analyze",
    title="Analyze with governed Ollama",
    description=(
        "Analyze code, text, or RAG context through the ReqSys Ollama gateway. "
        "Read-only; no repository, deployment, permission, or secret mutation."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def ollama_analyze(
    prompt: str,
    ctx: Context,
    context: str = "",
    model: str = "",
    task_type: Literal["code", "chat", "rag"] = "code",
    correlation_id: str = "",
) -> dict[str, object]:
    _authorize(ctx)
    return analyze(
        prompt=prompt,
        context=context,
        model=model,
        task_type=task_type,
        correlation_id=correlation_id,
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8010,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )
