#!/usr/bin/env python3
"""Runtime evidence gate for the ReqSys vault.

Runs a governed write/read/audit cycle before and after a controlled runtime
restart. Sensitive values are stored only in a local state file and are never
written to the public evidence artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0.0"
CONTRACT = "reqsys-cofre-runtime-evidence"


class GateError(RuntimeError):
    """Controlled evidence gate failure."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    payload: dict[str, Any]


class ApiClient:
    def __init__(self, base_url: str, admin_jwt: str, timeout: int, correlation_id: str):
        self.base_url = base_url.rstrip("/")
        self.admin_jwt = admin_jwt.strip()
        self.timeout = timeout
        self.correlation_id = correlation_id

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        vault_token: str | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> HttpResponse:
        headers = {
            "Accept": "application/json",
            "X-Correlation-ID": self.correlation_id,
            "User-Agent": "reqsys-cofre-runtime-evidence/1.0",
        }
        if self.admin_jwt:
            headers["Authorization"] = f"Bearer {self.admin_jwt}"
        if vault_token:
            headers["X-Vault-Token"] = vault_token
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:  # nosec B310
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                status = int(response.status)
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"detail": raw[:500]}
            status = int(exc.code)
        except (URLError, TimeoutError) as exc:
            raise GateError(f"Falha HTTP em {method} {path}: {exc}") from exc
        if status not in expected:
            detail = parsed.get("detail") or parsed.get("message") or "resposta inesperada"
            raise GateError(f"{method} {path} retornou HTTP {status}: {detail}")
        return HttpResponse(status=status, payload=parsed)


def _data(response: HttpResponse) -> dict[str, Any]:
    payload = response.payload
    value = payload.get("data", payload)
    if not isinstance(value, dict):
        raise GateError("Envelope de resposta inválido: campo data não é objeto")
    return value


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, mode)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_audit(client: ApiClient, actions: set[str]) -> dict[str, Any]:
    query = urlencode({"entidade": "cofre_segredo", "limit": 100})
    data = _data(client.request("GET", f"/v1/auditoria/eventos?{query}"))
    events = data.get("dados", [])
    matching = [
        event
        for event in events
        if event.get("correlation_id") == client.correlation_id and event.get("acao") in actions
    ]
    found = {str(event.get("acao")) for event in matching}
    missing = sorted(actions - found)
    if missing:
        raise GateError(f"Eventos de auditoria ausentes para correlation_id: {', '.join(missing)}")
    return {"required_actions": sorted(actions), "found_actions": sorted(found), "event_count": len(matching)}


def before_restart(args: argparse.Namespace) -> dict[str, Any]:
    client = ApiClient(args.base_url, args.admin_jwt, args.timeout, args.correlation_id)
    started = time.monotonic()
    status_before = _data(client.request("GET", "/v1/cofre/status"))
    initialized_by_gate = False
    if not bool(status_before.get("inicializado")):
        init_data = _data(client.request("POST", "/v1/cofre/init"))
        initialized_by_gate = init_data.get("status") == "inicializado"

    status_after = _data(client.request("GET", "/v1/cofre/status"))
    if not bool(status_after.get("inicializado")):
        raise GateError("Cofre continuou não inicializado após POST /v1/cofre/init")

    secret_key = f"REQSYS_EVIDENCE_{args.environment.upper()}_{secrets.token_hex(8).upper()}"
    secret_value = secrets.token_urlsafe(48)
    token_label = f"runtime-evidence-{args.environment}-{args.run_id}"
    token_data = _data(
        client.request(
            "POST",
            "/v1/cofre/tokens",
            payload={"label": token_label, "key_patterns": [secret_key]},
        )
    )
    scoped_token = str(token_data.get("token") or "")
    token_id = token_data.get("id")
    if not scoped_token or token_id is None:
        raise GateError("Criação de token escopado não retornou token e id")

    client.request("POST", "/v1/cofre/segredos", payload={"key": secret_key, "value": secret_value})
    read_data = _data(client.request("GET", f"/v1/cofre/segredos/{secret_key}", vault_token=scoped_token))
    if read_data.get("value") != secret_value:
        raise GateError("Valor lido antes do restart não corresponde ao valor gravado")

    forbidden_key = f"{secret_key}_OUT_OF_SCOPE"
    client.request(
        "GET",
        f"/v1/cofre/segredos/{forbidden_key}",
        vault_token=scoped_token,
        expected=(403,),
    )

    audit = _check_audit(client, {"COFRE_TOKEN_CRIADO", "COFRE_SEGREDO_GRAVADO", "COFRE_SEGREDO_LIDO"})
    state = {
        "secret_key": secret_key,
        "secret_value": secret_value,
        "secret_value_sha256": _sha256(secret_value),
        "scoped_token": scoped_token,
        "token_id": token_id,
        "token_label": token_label,
    }
    _write_json(Path(args.state_file), state, mode=0o600)
    return {
        "phase": "before_restart",
        "ok": True,
        "initialized_by_gate": initialized_by_gate,
        "vault_initialized": True,
        "vault_api_token_configured": bool(status_after.get("vault_api_token_configurado")),
        "vault_service": status_after.get("service"),
        "secret_key_sha256": _sha256(secret_key),
        "secret_value_sha256": state["secret_value_sha256"],
        "scoped_token_id": token_id,
        "scope_denial_validated": True,
        "audit": audit,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def after_restart(args: argparse.Namespace) -> dict[str, Any]:
    client = ApiClient(args.base_url, args.admin_jwt, args.timeout, args.correlation_id)
    started = time.monotonic()
    state_path = Path(args.state_file)
    if not state_path.exists():
        raise GateError("Arquivo de estado seguro não encontrado para fase pós-restart")
    state = _load_json(state_path)
    secret_key = str(state["secret_key"])
    secret_value = str(state["secret_value"])
    scoped_token = str(state["scoped_token"])
    token_id = int(state["token_id"])

    status = _data(client.request("GET", "/v1/cofre/status"))
    if not bool(status.get("inicializado")):
        raise GateError("Cofre perdeu inicialização após restart controlado")

    read_data = _data(client.request("GET", f"/v1/cofre/segredos/{secret_key}", vault_token=scoped_token))
    if read_data.get("value") != secret_value:
        raise GateError("Segredo não persistiu ou foi alterado após restart")

    client.request("DELETE", f"/v1/cofre/segredos/{secret_key}")
    client.request("DELETE", f"/v1/cofre/tokens/{token_id}")
    audit = _check_audit(
        client,
        {
            "COFRE_SEGREDO_LIDO",
            "COFRE_SEGREDO_REMOVIDO",
            "COFRE_TOKEN_REVOGADO",
        },
    )
    state_path.unlink(missing_ok=True)
    return {
        "phase": "after_restart",
        "ok": True,
        "vault_initialized": True,
        "persistence_after_restart": True,
        "cleanup_completed": True,
        "secret_key_sha256": _sha256(secret_key),
        "secret_value_sha256": _sha256(secret_value),
        "scoped_token_id": token_id,
        "audit": audit,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def build_evidence(args: argparse.Namespace, phase_result: dict[str, Any], *, error: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "ok": error is None and bool(phase_result.get("ok")),
        "environment": args.environment,
        "base_url": args.base_url.rstrip("/"),
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "workflow_sha": args.workflow_sha,
        "correlation_id": args.correlation_id,
        "generated_at_epoch": int(time.time()),
        "phase_result": phase_result,
        "error": error,
        "sensitive_values_exposed": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("before-restart", "after-restart"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--environment", required=True, choices=("dev", "stg"))
    parser.add_argument("--admin-jwt", default=os.getenv("COFRE_ADMIN_JWT", ""))
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--evidence-file", required=True)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--run-attempt", default=os.getenv("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--workflow-sha", default=os.getenv("GITHUB_SHA", "local"))
    args = parser.parse_args(argv)
    if not args.admin_jwt.strip():
        parser.error("--admin-jwt ou COFRE_ADMIN_JWT é obrigatório")
    if args.timeout < 1 or args.timeout > 120:
        parser.error("--timeout deve estar entre 1 e 120 segundos")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    evidence_path = Path(args.evidence_file)
    try:
        result = before_restart(args) if args.phase == "before-restart" else after_restart(args)
        evidence = build_evidence(args, result)
        _write_json(evidence_path, evidence)
        print(json.dumps({"ok": True, "phase": result["phase"], "evidence_file": str(evidence_path)}))
        return 0
    except Exception as exc:
        error = str(exc)
        evidence = build_evidence(args, {"phase": args.phase.replace("-", "_"), "ok": False}, error=error)
        _write_json(evidence_path, evidence)
        print(f"Cofre Runtime Evidence Gate falhou: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
