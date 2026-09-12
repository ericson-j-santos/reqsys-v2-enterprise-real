#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    status: str
    dsn_secret_name: str
    server_present: bool
    database_present: bool
    username_secret_present: bool
    password_secret_present: bool


def _run(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=input_text, text=True, capture_output=True, check=False)


def _secret(vault: str, name: str) -> str:
    proc = _run(["az", "keyvault", "secret", "show", "--vault-name", vault, "--name", name, "--query", "value", "-o", "tsv"])
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _build_dsn(server: str, database: str, username: str, password: str) -> str:
    if not all((server, database, username, password)):
        raise BootstrapError("MOVIMENTO_EMAIL_DSN_INPUT_INCOMPLETE")
    return (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};Database={database};UID={username};PWD={password};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )


def bootstrap(*, vault: str, server: str, database: str, username_secret: str, password_secret: str, dsn_secret_name: str, dry_run: bool = False) -> BootstrapResult:
    username = _secret(vault, username_secret)
    password = _secret(vault, password_secret)
    result = BootstrapResult(
        status="ready" if all((server, database, username, password)) else "blocked",
        dsn_secret_name=dsn_secret_name,
        server_present=bool(server),
        database_present=bool(database),
        username_secret_present=bool(username),
        password_secret_present=bool(password),
    )
    if result.status != "ready":
        return result
    dsn = _build_dsn(server, database, username, password)
    if dry_run:
        return result
    proc = _run([
        "az", "keyvault", "secret", "set",
        "--vault-name", vault,
        "--name", dsn_secret_name,
        "--value", dsn,
        "--tags", "owner=reqsys", "purpose=movimento-email", "managed-by=bootstrap_movimento_email_dsn",
        "--output", "none",
    ])
    dsn = ""  # best-effort cleanup; never print the value
    if proc.returncode != 0:
        raise BootstrapError("MOVIMENTO_EMAIL_DSN_KEYVAULT_WRITE_FAILED")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-name", default=os.getenv("REQSYS_KEY_VAULT_NAME", ""))
    parser.add_argument("--server", default=os.getenv("MOVIMENTO_EMAIL_SQL_SERVER", ""))
    parser.add_argument("--database", default=os.getenv("MOVIMENTO_EMAIL_SQL_DATABASE", ""))
    parser.add_argument("--username-secret", default=os.getenv("MOVIMENTO_EMAIL_SQL_USERNAME_SECRET", "movimento-email-sql-username"))
    parser.add_argument("--password-secret", default=os.getenv("MOVIMENTO_EMAIL_SQL_PASSWORD_SECRET", "movimento-email-sql-password"))
    parser.add_argument("--dsn-secret-name", default=os.getenv("MOVIMENTO_EMAIL_DSN_SECRET_NAME", "movimento-email-source-dsn"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.vault_name:
        print(json.dumps({"status": "blocked", "reason": "REQSYS_KEY_VAULT_NAME_MISSING"}))
        return 4
    try:
        result = bootstrap(
            vault=args.vault_name,
            server=args.server,
            database=args.database,
            username_secret=args.username_secret,
            password_secret=args.password_secret,
            dsn_secret_name=args.dsn_secret_name,
            dry_run=args.dry_run,
        )
    except BootstrapError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 5
    print(json.dumps(result.__dict__, sort_keys=True))
    return 0 if result.status == "ready" else 4


if __name__ == "__main__":
    raise SystemExit(main())
