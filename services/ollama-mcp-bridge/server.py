from __future__ import annotations

import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def _health_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "reqsys-ollama-mcp-bridge",
        "transport": "streamable-http",
        "mcp_path": "/mcp",
        "auth_configured": bool(os.getenv("OLLAMA_MCP_BEARER_TOKEN", "").strip()),
        "secret_exposed": False,
    }


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps(_health_payload(), sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def _start_health_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 8011), _HealthHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="reqsys-ollama-mcp-health",
        daemon=True,
    )
    thread.start()
    return server


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
    health_server = _start_health_server()
    try:
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8010,
            streamable_http_path="/mcp",
            stateless_http=True,
            json_response=True,
        )
    finally:
        health_server.shutdown()
        health_server.server_close()
