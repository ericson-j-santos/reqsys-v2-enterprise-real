#!/usr/bin/env python3
"""E2E local do ReqSys Codex usando Ollama cloud pelo caminho real.

Executa em ambiente isolado de DEV:
1) lê somente as três variáveis Ollama allowlisted do perfil Windows;
2) valida o provider direto ReqSys -> LLMGateway -> Ollama;
3) sobe temporariamente o gateway ou reutiliza explicitamente um gateway DEV saudável;
4) sobe backend temporário em porta configurável e autentica com identidade demo sintética;
5) chama POST /v1/codex/analyze com provider ollama_gateway;
6) encerra os processos e emite evidência JSON.

Não faz deploy, não toca produção e não lê segredos.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

MODEL_KEYS = ("CODEX_OLLAMA_MODEL", "CODEX_OLLAMA_GATEWAY_MODEL")
FALLBACK_MODEL_KEY = "CODEX_OLLAMA_FALLBACK_MODEL"
BASE_URL_KEY = "CODEX_OLLAMA_BASE_URL"
PROFILE_KEYS = (*MODEL_KEYS, FALLBACK_MODEL_KEY, BASE_URL_KEY)
CODE_PROMPT = """Você é um revisor sênior de Python. Corrija a função abaixo e proponha testes mínimos.

def normalize_ids(values):
    return list(set(str(v).strip() for v in values if v))

Requisitos obrigatórios:
1. preservar a ordem da primeira ocorrência;
2. deduplicar sem diferenciar maiúsculas/minúsculas;
3. ignorar None, string vazia e somente espaços;
4. preservar a grafia da primeira ocorrência;
5. incluir testes para duplicidade, caixa e vazios.

Responda de forma objetiva com diagnóstico, código corrigido e testes."""


class E2EError(RuntimeError):
    pass


def _read_windows_profile() -> dict[str, str | None]:
    if sys.platform != "win32":
        return {name: os.getenv(name) for name in PROFILE_KEYS}
    import winreg

    result: dict[str, str | None] = {}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ)
    except FileNotFoundError:
        return {name: None for name in PROFILE_KEYS}
    with key:
        for name in PROFILE_KEYS:
            try:
                value, _ = winreg.QueryValueEx(key, name)
                result[name] = str(value)
            except FileNotFoundError:
                result[name] = None
    return result


def _load_profile_into_env(expected_model: str, expected_fallback_model: str) -> dict[str, str]:
    values = _read_windows_profile()
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise E2EError("variáveis de perfil ausentes: " + ", ".join(missing))
    assert all(values[name] is not None for name in PROFILE_KEYS)
    resolved = {name: str(values[name]) for name in PROFILE_KEYS}
    if resolved["CODEX_OLLAMA_MODEL"] != expected_model:
        raise E2EError("CODEX_OLLAMA_MODEL diverge do modelo esperado")
    if resolved["CODEX_OLLAMA_GATEWAY_MODEL"] != expected_model:
        raise E2EError("CODEX_OLLAMA_GATEWAY_MODEL diverge do modelo esperado")
    if resolved["CODEX_OLLAMA_FALLBACK_MODEL"] != expected_fallback_model:
        raise E2EError("CODEX_OLLAMA_FALLBACK_MODEL diverge do fallback esperado")
    base = resolved["CODEX_OLLAMA_BASE_URL"].rstrip("/")
    if base not in {"http://127.0.0.1:11434", "http://localhost:11434"}:
        raise E2EError("CODEX_OLLAMA_BASE_URL não aponta para loopback esperado")
    for name, value in resolved.items():
        os.environ[name] = value
    return resolved


def _load_probe(root: Path):
    path = root / "scripts" / "ollama_capability_probe.py"
    spec = importlib.util.spec_from_file_location("ollama_capability_probe_e2e", path)
    if not spec or not spec.loader:
        raise E2EError("não foi possível carregar ollama_capability_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wait_http(url: str, process: subprocess.Popen[Any] | None, timeout: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise E2EError(f"processo encerrou antes de responder em {url}")
        try:
            response = requests.get(url, timeout=2)
            if response.status_code < 500:
                try:
                    return response.json()
                except ValueError:
                    return {"status_code": response.status_code, "text": response.text[:300]}
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(0.4)
    raise E2EError(f"timeout aguardando {url}: {last_error[-180:]}")


def _terminate(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise E2EError(f"porta {port} já está ocupada")


def _validate_port(port: int, *, name: str) -> int:
    if not 1 <= int(port) <= 65535:
        raise E2EError(f"{name} deve estar entre 1 e 65535")
    return int(port)


def _validate_reusable_gateway_health(data: dict[str, Any]) -> None:
    if data.get("status") != "ok":
        raise E2EError("gateway existente não está saudável")
    if data.get("service") != "reqsys-ollama-local-gateway":
        raise E2EError("serviço em gateway-port não é reqsys-ollama-local-gateway")
    env = str(data.get("env") or "").strip().lower()
    if env not in {"dev", "development", "test", "testing"}:
        raise E2EError("gateway existente não está em ambiente não-produtivo permitido")
    if bool(data.get("auth_required")):
        raise E2EError("gateway existente exige autenticação e não pode ser reutilizado por este E2E")


def _direct_provider(root: Path, probe: Any) -> dict[str, Any]:
    backend = root / "backend"
    sys.path.insert(0, str(backend))
    from app.core.config import settings
    from app.services.codex_governado import chamar_ollama

    if settings.codex_ollama_model != os.environ["CODEX_OLLAMA_MODEL"]:
        raise E2EError("Settings do ReqSys não resolveu CODEX_OLLAMA_MODEL do perfil")
    if settings.codex_ollama_base_url.rstrip("/") != os.environ["CODEX_OLLAMA_BASE_URL"].rstrip("/"):
        raise E2EError("Settings do ReqSys não resolveu CODEX_OLLAMA_BASE_URL do perfil")

    started = time.perf_counter()
    response = chamar_ollama(CODE_PROMPT)
    wall_ms = round((time.perf_counter() - started) * 1000, 2)
    quality = probe.score_code_response(response)
    return {
        "model": settings.codex_ollama_model,
        "base_url": settings.codex_ollama_base_url,
        "wall_ms": wall_ms,
        "quality": quality,
        "response_excerpt": response[:900],
    }


def _stack_env(
    profile: dict[str, str],
    temp_db: Path,
    *,
    gateway_url: str = "http://127.0.0.1:8008",
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(profile)
    env.update(
        {
            "APP_ENV": "development",
            "ENVIRONMENT": "development",
            "PUBLIC_ENVIRONMENT": "development",
            "ALLOW_DEMO_LOGIN": "true",
            "DATABASE_URL": f"sqlite:///{temp_db.as_posix()}",
            "CODEX_OLLAMA_GATEWAY_URL": gateway_url,
            "CODEX_OLLAMA_GATEWAY_API_KEY": "",
            "CODEX_OLLAMA_GATEWAY_TIMEOUT_SECONDS": "60",
            "REQSYS_ENV": "dev",
            "REQSYS_AUTH_REQUIRED": "false",
            "REQSYS_OLLAMA_BASE_URL": profile["CODEX_OLLAMA_BASE_URL"],
            "REQSYS_OLLAMA_FALLBACK_MODEL": profile["CODEX_OLLAMA_FALLBACK_MODEL"],
            "REQSYS_OLLAMA_TIMEOUT_SECONDS": "60",
            "REQSYS_OLLAMA_FALLBACK_TIMEOUT_SECONDS": "180",
            "CODEX_OLLAMA_FALLBACK_TIMEOUT_SECONDS": "180",
            "COFRE_API_URL": "",
            "COFRE_SERVICE_TOKEN": "",
        }
    )
    return env


def _full_endpoint(
    root: Path,
    profile: dict[str, str],
    probe: Any,
    *,
    gateway_port: int = 8008,
    backend_port: int = 8000,
    reuse_running_gateway: bool = False,
) -> dict[str, Any]:
    gateway_port = _validate_port(gateway_port, name="gateway-port")
    backend_port = _validate_port(backend_port, name="backend-port")
    if gateway_port == backend_port:
        raise E2EError("gateway-port e backend-port devem ser diferentes")

    gateway_url = f"http://127.0.0.1:{gateway_port}"
    backend_url = f"http://127.0.0.1:{backend_port}"
    _free_port(backend_port)
    if not reuse_running_gateway:
        _free_port(gateway_port)

    backend = root / "backend"
    gateway_src = root / "docs" / "ollama-local-gateway" / "bootstrap-files" / "src"

    temp = Path(tempfile.mkdtemp(prefix="reqsys-codex-cloud-e2e-"))
    env = _stack_env(profile, temp / "e2e.db", gateway_url=gateway_url)
    gateway_log = (temp / "gateway.log").open("w", encoding="utf-8")
    backend_log = (temp / "backend.log").open("w", encoding="utf-8")
    gateway: subprocess.Popen[Any] | None = None
    api: subprocess.Popen[Any] | None = None
    try:
        if reuse_running_gateway:
            gateway_health = _wait_http(f"{gateway_url}/health", None, 10)
            _validate_reusable_gateway_health(gateway_health)
        else:
            gateway = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "reqsys_ollama_gateway.main:app",
                    "--app-dir",
                    str(gateway_src),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(gateway_port),
                    "--log-level",
                    "warning",
                ],
                cwd=str(root),
                env=env,
                stdout=gateway_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            gateway_health = _wait_http(f"{gateway_url}/health", gateway, 30)
            _validate_reusable_gateway_health(gateway_health)

        fallback_probe = requests.post(
            f"{gateway_url}/v1/chat",
            json={
                "model": "__reqsys_cloud_unavailable__",
                "fallback_model": profile["CODEX_OLLAMA_FALLBACK_MODEL"],
                "task_type": "code",
                "prompt": "Responda somente com FALLBACK_OK.",
                "contexto": "negative-control",
                "entrada": "fallback",
                "correlation_id": "codex-cloud-fallback-20260919",
                "source": "reqsys-codex-e2e",
            },
            timeout=210,
        )
        fallback_probe.raise_for_status()
        fallback_data = fallback_probe.json()
        if not fallback_data.get("fallback_used"):
            raise E2EError("negative control não acionou fallback")
        if fallback_data.get("model") != profile["CODEX_OLLAMA_FALLBACK_MODEL"]:
            raise E2EError("negative control usou modelo de fallback inesperado")

        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--app-dir",
                str(backend),
                "--host",
                "127.0.0.1",
                "--port",
                str(backend_port),
                "--log-level",
                "warning",
            ],
            cwd=str(backend),
            env=env,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        backend_health = _wait_http(f"{backend_url}/health", api, 45)

        login = requests.post(
            f"{backend_url}/v1/auth/login",
            json={"email": "codex-e2e@example.com"},
            timeout=15,
        )
        login.raise_for_status()
        token = login.json()["data"]["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Correlation-Id": "codex-cloud-e2e-20260919",
        }

        status = requests.get(
            f"{backend_url}/v1/codex/status",
            headers=headers,
            timeout=15,
        )
        status.raise_for_status()

        started = time.perf_counter()
        analyze = requests.post(
            f"{backend_url}/v1/codex/analyze",
            headers=headers,
            json={
                "provider": "ollama_gateway",
                "contexto": "Validação E2E local do provider Codex governado no SHA corrente.",
                "entrada": CODE_PROMPT,
                "correlation_id": "codex-cloud-e2e-20260919",
                "publicar_no_reqsys": False,
            },
            timeout=90,
        )
        wall_ms = round((time.perf_counter() - started) * 1000, 2)
        analyze.raise_for_status()
        data = analyze.json()["data"]
        response = str(data.get("resultado") or "")
        quality = probe.score_code_response(response)
        if data.get("provider") != "ollama_gateway":
            raise E2EError("backend retornou provider diferente de ollama_gateway")
        if quality.get("passed") != quality.get("total"):
            raise E2EError("resposta E2E não passou o rubric 4/4")

        return {
            "evidence_dir": str(temp),
            "gateway_url": gateway_url,
            "gateway_reused": reuse_running_gateway,
            "gateway_health": gateway_health,
            "fallback_probe": {
                "requested_model": fallback_data.get("requested_model"),
                "model": fallback_data.get("model"),
                "fallback_used": fallback_data.get("fallback_used"),
                "latency_ms": fallback_data.get("latency_ms"),
                "response_excerpt": str(fallback_data.get("response") or "")[:200],
            },
            "backend_url": backend_url,
            "backend_health": backend_health,
            "codex_status": status.json()["data"],
            "provider": data.get("provider"),
            "correlation_id": data.get("correlation_id"),
            "backend_latency_ms": data.get("latencia_ms"),
            "wall_ms": wall_ms,
            "score_confianca": data.get("score_confianca"),
            "quality": quality,
            "response_excerpt": response[:900],
            "published_to_reqsys": bool((data.get("reqsys_publicacao") or {}).get("publicado")),
        }
    finally:
        _terminate(api)
        if not reuse_running_gateway:
            _terminate(gateway)
        backend_log.close()
        gateway_log.close()

def main() -> int:
    parser = argparse.ArgumentParser(description="Validação E2E ReqSys -> Ollama cloud")
    parser.add_argument("--expected-model", default="gemma4:31b-cloud")
    parser.add_argument("--expected-fallback-model", default="gemma4:26b-q8-code")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--gateway-port", type=int, default=8008)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument(
        "--reuse-running-gateway",
        action="store_true",
        help="Reutiliza somente um reqsys-ollama-local-gateway saudável em DEV/test.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        profile = _load_profile_into_env(args.expected_model, args.expected_fallback_model)
        probe = _load_probe(root)
        direct = _direct_provider(root, probe)
        full = _full_endpoint(
            root,
            profile,
            probe,
            gateway_port=args.gateway_port,
            backend_port=args.backend_port,
            reuse_running_gateway=args.reuse_running_gateway,
        )
        result = {
            "result": "E2E_OK",
            "root": str(root),
            "expected_model": args.expected_model,
            "expected_fallback_model": args.expected_fallback_model,
            "profile": profile,
            "direct_provider": direct,
            "full_endpoint": full,
            "production_touched": False,
            "deploy_performed": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "result": "E2E_BLOCKED",
                    "error": str(exc)[:500],
                    "production_touched": False,
                    "deploy_performed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
