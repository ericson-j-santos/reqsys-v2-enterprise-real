#!/usr/bin/env python3
"""Validação rápida, somente leitura e sem cloud do Ollama local no PC24x7."""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CallResult:
    ok: bool
    latency_ms: int
    model: str | None
    response_length: int
    sentinel_ok: bool
    eval_count: int | None = None
    eval_tokens_per_second: float | None = None
    fallback_used: bool | None = None
    error: str | None = None


def http_json(url: str, *, payload: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"http_{exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(type(exc).__name__) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid_json") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("invalid_payload")
    return parsed


def installed_models() -> list[dict[str, Any]]:
    data = http_json("http://127.0.0.1:11434/api/tags", timeout=15)
    items = data.get("models")
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        out.append(
            {
                "name": str(item.get("name") or ""),
                "size_bytes": int(item.get("size") or 0),
                "parameter_size": str(details.get("parameter_size") or ""),
                "quantization_level": str(details.get("quantization_level") or ""),
            }
        )
    return out


def loaded_models() -> list[dict[str, Any]]:
    data = http_json("http://127.0.0.1:11434/api/ps", timeout=15)
    items = data.get("models")
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": str(item.get("name") or ""),
                "size_bytes": int(item.get("size") or 0),
                "size_vram_bytes": int(item.get("size_vram") or 0),
            }
        )
    return out


def direct_generate(model: str, sentinel: str, timeout: int) -> CallResult:
    started = time.perf_counter()
    try:
        data = http_json(
            "http://127.0.0.1:11434/api/generate",
            payload={
                "model": model,
                "prompt": f"Responda somente com {sentinel}. Sem explicação.",
                "stream": False,
                "keep_alive": "5m",
                "options": {"temperature": 0},
            },
            timeout=timeout,
        )
        response = str(data.get("response") or "").strip()
        eval_count = data.get("eval_count")
        eval_duration = data.get("eval_duration")
        tps = None
        if isinstance(eval_count, int) and isinstance(eval_duration, int) and eval_duration > 0:
            tps = round(eval_count / (eval_duration / 1_000_000_000), 2)
        return CallResult(
            ok=bool(response),
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=str(data.get("model") or model),
            response_length=len(response),
            sentinel_ok=sentinel in response,
            eval_count=eval_count if isinstance(eval_count, int) else None,
            eval_tokens_per_second=tps,
        )
    except RuntimeError as exc:
        return CallResult(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=None,
            response_length=0,
            sentinel_ok=False,
            error=str(exc),
        )


def gateway_generate(model: str, sentinel: str, timeout: int, correlation_id: str) -> CallResult:
    started = time.perf_counter()
    try:
        data = http_json(
            "http://127.0.0.1:8008/v1/chat",
            payload={
                "model": model,
                "fallback_model": model,
                "task_type": "chat",
                "prompt": f"Responda somente com {sentinel}. Sem explicação.",
                "contexto": "",
                "entrada": "",
                "correlation_id": correlation_id,
                "source": "pc24x7-local-benchmark",
            },
            timeout=timeout,
        )
        response = str(data.get("response") or "").strip()
        return CallResult(
            ok=bool(response),
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=str(data.get("model") or "") or None,
            response_length=len(response),
            sentinel_ok=sentinel in response,
            fallback_used=bool(data.get("fallback_used", False)),
        )
    except RuntimeError as exc:
        return CallResult(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=None,
            response_length=0,
            sentinel_ok=False,
            error=str(exc),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemma4:26b-q8-code")
    parser.add_argument("--timeout", type=int, default=150)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()

    sentinel = "OLLAMA_LOCAL_OK"
    evidence: dict[str, Any] = {
        "correlation_id": args.correlation_id,
        "requested_model": args.model,
        "direct_endpoint": "127.0.0.1:11434",
        "gateway_endpoint": "127.0.0.1:8008",
        "cloud_called": False,
        "model_pull_performed": False,
        "secrets_read": False,
        "production_touched": False,
    }

    try:
        models = installed_models()
    except RuntimeError as exc:
        evidence.update({"ok": False, "state": "ollama_unreachable", "error": str(exc)})
        print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
        return 3

    evidence["installed_models"] = models
    if args.model not in {item["name"] for item in models}:
        evidence.update({"ok": False, "state": "requested_model_not_installed"})
        print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
        return 4

    direct = direct_generate(args.model, sentinel, args.timeout)
    evidence["direct"] = asdict(direct)

    try:
        evidence["loaded_after_direct"] = loaded_models()
    except RuntimeError as exc:
        evidence["loaded_after_direct_error"] = str(exc)

    gateway = gateway_generate(args.model, sentinel, args.timeout, args.correlation_id)
    evidence["gateway"] = asdict(gateway)

    evidence["ok"] = bool(
        direct.ok
        and direct.sentinel_ok
        and gateway.ok
        and gateway.sentinel_ok
        and gateway.model == args.model
    )
    evidence["state"] = "validated" if evidence["ok"] else "validation_failed"
    print(json.dumps(evidence, ensure_ascii=True, sort_keys=True))
    return 0 if evidence["ok"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
