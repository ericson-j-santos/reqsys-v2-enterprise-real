#!/usr/bin/env python3
"""Diagnóstico governado de capacidade do Ollama local/cloud.

Consulta somente a API HTTP local do Ollama por padrão, sem ler segredos.
Mede:
- versão e modelos disponíveis/ativos;
- contexto reportado pelo runtime/modelo;
- geração de código controlada;
- suporte real a tool calling;
- latências e métricas de tokens expostas pelo Ollama.

Saída padrão: um único JSON em stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT = 120
MAX_EXCERPT = 2400


class ProbeError(RuntimeError):
    """Falha controlada do probe."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_request(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, dict[str, Any], float]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(response.status)
    except HTTPError as exc:
        raw = exc.read()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        detail = raw.decode("utf-8", errors="replace")[:MAX_EXCERPT]
        raise ProbeError(f"HTTP {exc.code} em {url}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProbeError(f"falha de conexão em {url}: {exc}") from exc
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    try:
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"resposta não JSON em {url}") from exc
    if not isinstance(data, dict):
        raise ProbeError(f"resposta inesperada em {url}: {type(data).__name__}")
    return status, data, elapsed_ms


def _ensure_loopback(base_url: str, allow_non_loopback: bool) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProbeError("base-url inválida")
    host = parsed.hostname.lower()
    loopback_names = {"localhost", "127.0.0.1", "::1"}
    if host not in loopback_names and not allow_non_loopback:
        raise ProbeError(
            "base-url não é loopback; use --allow-non-loopback somente quando explicitamente autorizado"
        )
    return base_url.rstrip("/")


def _model_names(items: list[Any]) -> list[str]:
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return names


def select_model(
    explicit: str | None,
    running_models: list[dict[str, Any]],
    available_models: list[dict[str, Any]],
    env_model: str | None = None,
) -> tuple[str, str]:
    if explicit:
        return explicit, "explicit"
    running = _model_names(running_models)
    if running:
        return running[0], "running"
    if env_model:
        return env_model, "environment"
    available = _model_names(available_models)
    preferred = [
        name
        for name in available
        if "cloud" in name.casefold() and "31b" in name.casefold()
    ]
    if preferred:
        return preferred[0], "available_cloud_31b"
    if available:
        return available[0], "available_first"
    raise ProbeError("nenhum modelo Ollama foi encontrado")


def extract_context_length(
    show_data: dict[str, Any],
    running_models: list[dict[str, Any]],
    selected_model: str,
) -> dict[str, Any]:
    candidates: list[tuple[str, int]] = []
    for item in running_models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "")
        if name != selected_model:
            continue
        value = item.get("context_length")
        if isinstance(value, int) and value > 0:
            candidates.append(("api_ps.context_length", value))

    model_info = show_data.get("model_info")
    if isinstance(model_info, dict):
        for key, value in model_info.items():
            if str(key).endswith(".context_length") and isinstance(value, int) and value > 0:
                candidates.append((f"api_show.model_info.{key}", value))

    parameters = show_data.get("parameters")
    if isinstance(parameters, str):
        for line in parameters.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].strip().casefold() == "num_ctx":
                try:
                    value = int(parts[1])
                except ValueError:
                    continue
                if value > 0:
                    candidates.append(("api_show.parameters.num_ctx", value))

    if not candidates:
        return {"reported": None, "sources": []}
    return {
        "reported": max(value for _, value in candidates),
        "sources": [{"source": source, "value": value} for source, value in candidates],
    }


def _duration_metrics(data: dict[str, Any], wall_ms: float) -> dict[str, Any]:
    def nanos_to_ms(key: str) -> float | None:
        value = data.get(key)
        if isinstance(value, (int, float)):
            return round(float(value) / 1_000_000, 2)
        return None

    eval_count = data.get("eval_count")
    eval_duration = data.get("eval_duration")
    tokens_per_second = None
    if isinstance(eval_count, int) and eval_count >= 0 and isinstance(eval_duration, (int, float)) and eval_duration > 0:
        tokens_per_second = round(eval_count / (float(eval_duration) / 1_000_000_000), 2)

    return {
        "wall_ms": wall_ms,
        "total_ms": nanos_to_ms("total_duration"),
        "load_ms": nanos_to_ms("load_duration"),
        "prompt_eval_ms": nanos_to_ms("prompt_eval_duration"),
        "eval_ms": nanos_to_ms("eval_duration"),
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": eval_count,
        "tokens_per_second": tokens_per_second,
    }


def _excerpt(value: Any) -> str:
    text = str(value or "")
    return text[:MAX_EXCERPT]


def score_code_response(text: str) -> dict[str, Any]:
    folded = text.casefold()
    checks = {
        "stable_order": any(term in folded for term in ("ordem", "order", "seen")),
        "case_insensitive": any(term in folded for term in ("casefold", "lower()", "case-insensitive", "maiúsc", "minus")),
        "blank_handling": any(term in folded for term in ("strip", "blank", "vazio", "empty")),
        "tests": any(term in folded for term in ("pytest", "assert", "unittest", "test_")),
    }
    return {"checks": checks, "passed": sum(checks.values()), "total": len(checks)}


def run_code_benchmark(base: str, model: str, timeout: int, num_ctx: int | None) -> dict[str, Any]:
    prompt = """Você é um revisor sênior de Python. Corrija a função abaixo e proponha testes mínimos.

def normalize_ids(values):
    return list(set(str(v).strip() for v in values if v))

Requisitos obrigatórios:
1. preservar a ordem da primeira ocorrência;
2. deduplicar sem diferenciar maiúsculas/minúsculas;
3. ignorar None, string vazia e somente espaços;
4. preservar a grafia da primeira ocorrência;
5. incluir testes para duplicidade, caixa e vazios.

Responda de forma objetiva com diagnóstico, código corrigido e testes."""
    options: dict[str, Any] = {"temperature": 0}
    if num_ctx:
        options["num_ctx"] = num_ctx
    _, data, wall_ms = _json_request(
        "POST",
        f"{base}/api/generate",
        {"model": model, "prompt": prompt, "stream": False, "options": options},
        timeout=timeout,
    )
    response = str(data.get("response") or "")
    return {
        "ok": bool(response.strip()),
        "quality": score_code_response(response),
        "metrics": _duration_metrics(data, wall_ms),
        "response_excerpt": _excerpt(response),
    }


def run_tool_call_benchmark(base: str, model: str, timeout: int, num_ctx: int | None) -> dict[str, Any]:
    options: dict[str, Any] = {"temperature": 0}
    if num_ctx:
        options["num_ctx"] = num_ctx
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Use a ferramenta get_repo_state exatamente uma vez para consultar "
                    "ericson-j-santos/reqsys-v2-enterprise-real. Não invente o resultado da ferramenta."
                ),
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_repo_state",
                    "description": "Obtém o estado atual de um repositório Git autorizado.",
                    "parameters": {
                        "type": "object",
                        "properties": {"repo": {"type": "string"}},
                        "required": ["repo"],
                    },
                },
            }
        ],
        "options": options,
    }
    _, data, wall_ms = _json_request("POST", f"{base}/api/chat", payload, timeout=timeout)
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    calls = message.get("tool_calls") if isinstance(message, dict) else None
    calls = calls if isinstance(calls, list) else []
    first = calls[0] if calls and isinstance(calls[0], dict) else {}
    function = first.get("function") if isinstance(first.get("function"), dict) else {}
    name = function.get("name")
    arguments = function.get("arguments")
    expected_repo = "ericson-j-santos/reqsys-v2-enterprise-real"
    repo_ok = False
    if isinstance(arguments, dict):
        repo_ok = arguments.get("repo") == expected_repo
    return {
        "ok": bool(calls) and name == "get_repo_state" and repo_ok,
        "tool_call_count": len(calls),
        "tool_name": name,
        "arguments_match": repo_ok,
        "assistant_content_excerpt": _excerpt(message.get("content") if isinstance(message, dict) else ""),
        "metrics": _duration_metrics(data, wall_ms),
    }


def collect(args: argparse.Namespace) -> dict[str, Any]:
    base = _ensure_loopback(args.base_url, args.allow_non_loopback)
    _, version_data, version_ms = _json_request("GET", f"{base}/api/version", timeout=args.timeout)
    _, ps_data, ps_ms = _json_request("GET", f"{base}/api/ps", timeout=args.timeout)
    _, tags_data, tags_ms = _json_request("GET", f"{base}/api/tags", timeout=args.timeout)

    running_models = ps_data.get("models") if isinstance(ps_data.get("models"), list) else []
    available_models = tags_data.get("models") if isinstance(tags_data.get("models"), list) else []
    env_model = os.getenv("CODEX_OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL")
    model, selected_by = select_model(args.model, running_models, available_models, env_model)

    _, show_data, show_ms = _json_request(
        "POST", f"{base}/api/show", {"model": model}, timeout=args.timeout
    )
    context = extract_context_length(show_data, running_models, model)
    capabilities = show_data.get("capabilities")
    if not isinstance(capabilities, list):
        capabilities = []

    result: dict[str, Any] = {
        "timestamp": utc_now(),
        "host": socket.gethostname(),
        "base_url": base,
        "ollama_version": version_data.get("version"),
        "request_latency_ms": {
            "version": version_ms,
            "ps": ps_ms,
            "tags": tags_ms,
            "show": show_ms,
        },
        "selected_model": model,
        "selected_by": selected_by,
        "cloud_hint": "cloud" in model.casefold(),
        "running_models": _model_names(running_models),
        "available_models": _model_names(available_models),
        "context": context,
        "capabilities": capabilities,
        "requested_num_ctx_override": args.num_ctx,
    }

    if not args.inventory_only:
        benchmarks: dict[str, Any] = {}
        try:
            benchmarks["code"] = run_code_benchmark(base, model, args.timeout, args.num_ctx)
        except ProbeError as exc:
            benchmarks["code"] = {"ok": False, "error": str(exc)}
        try:
            benchmarks["tool_calling"] = run_tool_call_benchmark(base, model, args.timeout, args.num_ctx)
        except ProbeError as exc:
            benchmarks["tool_calling"] = {"ok": False, "error": str(exc)}
        result["benchmarks"] = benchmarks

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe governado de capacidade do Ollama")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--num-ctx", type=int, default=None)
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--allow-non-loopback", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout < 1 or args.timeout > 900:
        print(json.dumps({"ok": False, "error": "timeout deve estar entre 1 e 900"}))
        return 2
    if args.num_ctx is not None and args.num_ctx < 1024:
        print(json.dumps({"ok": False, "error": "num-ctx deve ser >= 1024"}))
        return 2
    try:
        result = collect(args)
        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ProbeError as exc:
        print(
            json.dumps(
                {"ok": False, "timestamp": utc_now(), "host": socket.gethostname(), "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
