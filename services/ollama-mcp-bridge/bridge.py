from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

_CORRELATION_RE = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")
_DEFAULT_ALLOWED_MODELS = ("gemma4:31b-cloud", "gemma4:26b-q8-code")
_ALLOWED_TASK_TYPES = {"code", "chat", "rag"}


class BridgeError(RuntimeError):
    """Falha segura do bridge MCP para o Ollama."""


@dataclass(frozen=True)
class BridgeSettings:
    gateway_url: str
    gateway_api_key: str
    allowed_models: tuple[str, ...]
    default_model: str
    fallback_model: str
    timeout_seconds: int


def _csv_models(value: str) -> tuple[str, ...]:
    items = tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    if not items:
        raise BridgeError("ollama_model_allowlist_empty")
    return items


def _validate_gateway_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 8008
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise BridgeError("ollama_gateway_must_be_loopback_8008")
    return value.rstrip("/")


def load_settings(env: dict[str, str] | None = None) -> BridgeSettings:
    source = os.environ if env is None else env
    allowed = _csv_models(
        source.get("OLLAMA_MCP_ALLOWED_MODELS", ",".join(_DEFAULT_ALLOWED_MODELS))
    )
    default_model = source.get("OLLAMA_MCP_DEFAULT_MODEL", allowed[0]).strip()
    fallback_model = source.get(
        "OLLAMA_MCP_FALLBACK_MODEL",
        "gemma4:26b-q8-code" if "gemma4:26b-q8-code" in allowed else allowed[-1],
    ).strip()
    if default_model not in allowed or fallback_model not in allowed:
        raise BridgeError("ollama_model_not_allowlisted")
    timeout = int(source.get("OLLAMA_MCP_TIMEOUT_SECONDS", "60"))
    if timeout < 1 or timeout > 180:
        raise BridgeError("ollama_timeout_out_of_range")
    return BridgeSettings(
        gateway_url=_validate_gateway_url(
            source.get("OLLAMA_MCP_GATEWAY_URL", "http://127.0.0.1:8008")
        ),
        gateway_api_key=source.get("OLLAMA_MCP_GATEWAY_API_KEY", "").strip(),
        allowed_models=allowed,
        default_model=default_model,
        fallback_model=fallback_model,
        timeout_seconds=timeout,
    )


def _correlation_id(value: str) -> str:
    candidate = value.strip() or f"github-copilot-ollama-{uuid4()}"
    if not _CORRELATION_RE.fullmatch(candidate):
        raise BridgeError("invalid_correlation_id")
    return candidate


def _validate_text(name: str, value: str, max_length: int) -> str:
    text = value.strip()
    if not text:
        raise BridgeError(f"{name}_required")
    if len(text) > max_length:
        raise BridgeError(f"{name}_too_long")
    return text


def _gateway_request(
    settings: BridgeSettings,
    *,
    prompt: str,
    context: str,
    model: str,
    task_type: str,
    correlation_id: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "fallback_model": settings.fallback_model,
        "task_type": task_type,
        "prompt": prompt,
        "contexto": context,
        "entrada": "",
        "correlation_id": correlation_id,
        "source": "github-copilot-ollama-mcp",
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Correlation-Id": correlation_id,
    }
    if settings.gateway_api_key:
        headers["X-API-Key"] = settings.gateway_api_key
    request = urllib.request.Request(
        f"{settings.gateway_url}/v1/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
    except (
        OSError,
        TimeoutError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        raise BridgeError("ollama_gateway_unavailable") from exc

    if not isinstance(data, dict) or not str(data.get("response") or "").strip():
        raise BridgeError("ollama_gateway_invalid_response")
    effective_model = str(data.get("model") or "").strip()
    if effective_model not in settings.allowed_models:
        raise BridgeError("ollama_gateway_model_not_allowlisted")
    return data


def analyze(
    *,
    prompt: str,
    context: str = "",
    model: str = "",
    task_type: str = "code",
    correlation_id: str = "",
    settings: BridgeSettings | None = None,
) -> dict[str, Any]:
    cfg = settings or load_settings()
    selected_model = model.strip() or cfg.default_model
    if selected_model not in cfg.allowed_models:
        raise BridgeError("ollama_model_not_allowlisted")
    if task_type not in _ALLOWED_TASK_TYPES:
        raise BridgeError("ollama_task_type_not_allowed")

    clean_prompt = _validate_text("prompt", prompt, 50_000)
    clean_context = context.strip()
    if len(clean_context) > 12_000:
        raise BridgeError("context_too_long")
    cid = _correlation_id(correlation_id)

    started = time.perf_counter()
    data = _gateway_request(
        cfg,
        prompt=clean_prompt,
        context=clean_context,
        model=selected_model,
        task_type=task_type,
        correlation_id=cid,
    )
    elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
    return {
        "response": str(data["response"]),
        "requested_model": selected_model,
        "model": str(data["model"]),
        "fallback_used": bool(data.get("fallback_used", False)),
        "provider": "ollama_gateway",
        "correlation_id": cid,
        "latency_ms": int(data.get("latency_ms") or elapsed_ms),
    }
