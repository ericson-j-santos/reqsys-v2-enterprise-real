#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_PROCEDURE = "integration.usp_ConsultarPorIdentificadores"


@dataclass(frozen=True)
class Candidate:
    source: str
    value: str


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _cofre_get(base_url: str, token: str, key: str) -> str | None:
    if not base_url.strip() or not token.strip():
        return None
    endpoint = base_url.rstrip("/") + f"/v1/cofre/segredos/{key}"
    request = urllib.request.Request(
        endpoint,
        headers={"Accept": "application/json", "X-Vault-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 - URL operada via secret
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"cofre_http_{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("cofre_rede_indisponivel") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("cofre_json_invalido") from exc

    value = payload.get("data", {}).get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def validate_sql_candidate(dsn: str, procedure: str) -> tuple[bool, str | None]:
    try:
        import pyodbc
    except ImportError:
        return False, "pyodbc_ausente"

    connection = None
    try:
        connection = pyodbc.connect(dsn, timeout=10)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT CASE WHEN OBJECT_ID(?, 'P') IS NULL THEN 0 ELSE 1 END",
            procedure,
        )
        row = cursor.fetchone()
        if row and int(row[0]) == 1:
            return True, None
        return False, "stored_procedure_ausente"
    except Exception:
        return False, "sql_connect_or_query_failed"
    finally:
        if connection is not None:
            connection.close()


def collect_candidates(
    env: dict[str, str],
    *,
    vault_getter: Callable[[str, str, str], str | None] = _cofre_get,
) -> tuple[list[Candidate], list[dict[str, object]]]:
    candidates: list[Candidate] = []
    diagnostics: list[dict[str, object]] = []
    seen_values: set[str] = set()

    def add(source: str, value: str | None) -> None:
        text = str(value or "").strip()
        diagnostics.append({"source": source, "present": bool(text)})
        if text and text not in seen_values:
            seen_values.add(text)
            candidates.append(Candidate(source=source, value=text))

    add("github:INTEGRATION_E2E_SQL_DSN", env.get("INTEGRATION_E2E_SQL_DSN", ""))
    add("github:MOVIMENTO_EMAIL_SOURCE_DSN", env.get("MOVIMENTO_EMAIL_SOURCE_DSN", ""))

    base_url = env.get("COFRE_API_URL", "").strip()
    vault_token = env.get("VAULT_API_TOKEN", "").strip()
    vault_ready = bool(base_url and vault_token)
    diagnostics.append({"source": "cofre", "configured": vault_ready})

    if vault_ready:
        for key in ("INTEGRATION_E2E_SQL_DSN", "MOVIMENTO_EMAIL_SOURCE_DSN"):
            source = f"cofre:{key}"
            try:
                add(source, vault_getter(base_url, vault_token, key))
            except RuntimeError as exc:
                diagnostics.append({"source": source, "present": False, "error": str(exc)})

    return candidates, diagnostics


def resolve_sql_dsn(
    env: dict[str, str],
    *,
    procedure: str = DEFAULT_PROCEDURE,
    validator: Callable[[str, str], tuple[bool, str | None]] = validate_sql_candidate,
    vault_getter: Callable[[str, str, str], str | None] = _cofre_get,
) -> tuple[Candidate | None, dict[str, object]]:
    candidates, diagnostics = collect_candidates(env, vault_getter=vault_getter)
    attempts: list[dict[str, object]] = []

    for candidate in candidates:
        _mask(candidate.value)
        ok, reason = validator(candidate.value, procedure)
        attempts.append(
            {
                "source": candidate.source,
                "connection_and_procedure_valid": ok,
                "reason": reason,
            }
        )
        if ok:
            return candidate, {
                "status": "resolved",
                "procedure": procedure,
                "source": candidate.source,
                "attempts": attempts,
                "discovery": diagnostics,
                "secret_exposed": False,
            }

    return None, {
        "status": "blocked",
        "procedure": procedure,
        "source": None,
        "attempts": attempts,
        "discovery": diagnostics,
        "secret_exposed": False,
        "blocked_code": "sql_dsn_validado_ausente",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve DSN SQL DEV sem expor credenciais")
    parser.add_argument("--github-env", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--procedure", default=os.getenv("INTEGRATION_E2E_SQL_PROCEDURE", DEFAULT_PROCEDURE))
    args = parser.parse_args()

    candidate, evidence = resolve_sql_dsn(dict(os.environ), procedure=args.procedure.strip() or DEFAULT_PROCEDURE)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if candidate is None:
        print(json.dumps({"status": "blocked", "blocked_code": evidence["blocked_code"]}, ensure_ascii=False))
        return 2

    with args.github_env.open("a", encoding="utf-8") as handle:
        handle.write(f"INTEGRATION_E2E_SQL_DSN={candidate.value}\n")
    print(json.dumps({"status": "resolved", "source": candidate.source, "procedure_valid": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
