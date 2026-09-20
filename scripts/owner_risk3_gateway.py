#!/usr/bin/env python3
"""Owner-only Risk 3 gateway.

O Command Gateway canônico continua recusando Risk 3. Esta rota aceita duas
formas controladas em local/DEV:
1. ação exata cadastrada na allowlist privada local;
2. modo de desenvolvimento temporário, explícito e auditado, somente para
   scripts Python versionados em worktree Git limpo.

HML/PROD, operações destrutivas, desligamento/reboot, billing, privilégios
administrativos amplos e passagem explícita de segredos continuam bloqueados.
"""
from __future__ import annotations

import argparse
import fnmatch
import getpass
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

EXIT_POLICY = 20
EXIT_COMMAND = 22
EXIT_TIMEOUT = 24
EXIT_EXPIRED = 26

SAFE_ENVIRONMENTS = {"local", "dev"}
DEV_MODE_REASON = "standard_gold_development"
DEV_MODE_MAX_DAYS = 30
DEV_EXECUTABLES = {"python", "python3"}
FORBIDDEN_EXECUTABLES = {
    "cmd", "powershell", "pwsh", "bash", "sh", "wsl", "ssh", "scp"
}
FORBIDDEN_ROLE_NAMES = {
    "owner", "contributor", "user access administrator",
    "role based access control administrator",
}
FORBIDDEN_DESTRUCTIVE_TOKENS = {
    "delete", "purge", "destroy", "drop", "prune", "reset", "format", "wipe"
}
SHELL_META = ("&&", "||", ";", "|", ">", "<", "`", "$(")
SECRET_OPTION_RE = re.compile(
    r"(?i)(?:^|[-_])(token|secret|password|passwd|api[-_]?key|client[-_]?secret)(?:$|[-_=])"
)
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(token|secret|password|passwd|api[_-]?key|authorization)\b\s*[:=]\s*\S+"
)
PRODUCTION_MARKER_RE = re.compile(r"(?i)(^|[/:._-])(prod|production|stg|stage|staging|hml|homolog)([/:._-]|$)")
HOST_POWER_MARKER_RE = re.compile(r"(?i)(?:^|[\\/:._-])(reboot|shutdown|poweroff)(?:$|[\\/:._-])")


class Risk3Error(RuntimeError):
    def __init__(self, message: str, exit_code: int = EXIT_POLICY) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Risk3Error("expires_at inválido") from exc
    if parsed.tzinfo is None:
        raise Risk3Error("expires_at deve conter timezone")
    return parsed.astimezone(timezone.utc)


def owner_fingerprint() -> str:
    identity = f"{getpass.getuser()}@{socket.gethostname()}".encode("utf-8", errors="replace")
    return hashlib.sha256(identity).hexdigest()


def default_state_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "ReqSys" / "CommandGateway"
    return Path.home() / ".reqsys-command-gateway"


def default_config_path() -> Path:
    return default_state_dir() / "owner-risk3-exceptions.local.json"


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_local_config(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        raise Risk3Error("configuração risco 3 deve usar caminho absoluto")
    if path.name != "owner-risk3-exceptions.local.json":
        raise Risk3Error("arquivo local de exceção possui nome inesperado")
    if not path.is_file():
        raise Risk3Error("configuração local de risco 3 inexistente")
    if os.name != "nt":
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            raise Risk3Error("configuração local deve ser privada (chmod 600)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Risk3Error("configuração local de risco 3 inválida") from exc
    if data.get("version") != 1 or data.get("enabled") is not True:
        raise Risk3Error("exceção risco 3 local não está habilitada")
    expected = data.get("owner_fingerprint")
    if not isinstance(expected, str) or expected != owner_fingerprint():
        raise Risk3Error("exceção risco 3 não pertence ao usuário/máquina atual")
    return data


def normalize_executable(value: str) -> str:
    exe = Path(value).name.casefold()
    return exe[:-4] if exe.endswith(".exe") else exe


def normalize_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").rstrip("/").casefold()


def matches_allowed_root(cwd: Path, patterns: list[str]) -> bool:
    current = normalize_path(cwd.resolve())
    return any(fnmatch.fnmatch(current, normalize_path(pattern)) for pattern in patterns)


def _guard_common(action_id: str, requested_scope: str, command: list[str], *, strict_secret_options: bool) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", action_id):
        raise Risk3Error("action_id inválido")
    if PRODUCTION_MARKER_RE.search(action_id) or PRODUCTION_MARKER_RE.search(requested_scope):
        raise Risk3Error("HML/STG/PROD permanecem bloqueados")
    if HOST_POWER_MARKER_RE.search(action_id) or HOST_POWER_MARKER_RE.search(requested_scope):
        raise Risk3Error("reinicialização/desligamento de host permanece bloqueado")
    if not command or not all(isinstance(item, str) and item for item in command):
        raise Risk3Error("comando inválido")
    exe = normalize_executable(command[0])
    if exe in FORBIDDEN_EXECUTABLES:
        raise Risk3Error(f"executável proibido mesmo em risco 3: {exe}")
    if any(meta in arg for arg in command for meta in SHELL_META):
        raise Risk3Error("metacaractere/composição de shell proibido")
    if any(HOST_POWER_MARKER_RE.search(arg) for arg in command):
        raise Risk3Error("reinicialização/desligamento de host permanece bloqueado")
    if any(PRODUCTION_MARKER_RE.search(arg) for arg in command):
        raise Risk3Error("HML/STG/PROD permanecem bloqueados")
    lowered = [arg.casefold() for arg in command[1:]]
    if exe == "az" and len(lowered) >= 2 and lowered[0] == "keyvault" and lowered[1] == "secret":
        raise Risk3Error("leitura/escrita direta de segredos permanece bloqueada")
    if any(SECRET_VALUE_RE.search(arg) for arg in command):
        raise Risk3Error("valor potencialmente secreto embutido no comando")
    if strict_secret_options:
        secret_options = command[1:]
    else:
        secret_options = [arg for arg in command[1:] if arg.startswith("-")]
    if any(SECRET_OPTION_RE.search(arg) for arg in secret_options):
        raise Risk3Error("opção de segredo/credencial proibida em risco 3")
    if any(token in FORBIDDEN_DESTRUCTIVE_TOKENS for token in lowered):
        raise Risk3Error("operação destrutiva permanece bloqueada")
    if any(role in FORBIDDEN_ROLE_NAMES for role in lowered):
        raise Risk3Error("papel administrativo amplo permanece bloqueado")
    if "billing" in " ".join(lowered) or "microsoft.billing" in requested_scope.casefold():
        raise Risk3Error("billing permanece bloqueado")


def validate_action(action_id: str, requested_scope: str, action: dict[str, Any]) -> list[str]:
    environment = str(action.get("environment", "")).casefold()
    if environment not in SAFE_ENVIRONMENTS:
        raise Risk3Error("risco 3 proprietário limitado a local/dev")
    configured_scope = action.get("scope")
    if not isinstance(configured_scope, str) or not configured_scope or configured_scope != requested_scope:
        raise Risk3Error("escopo não corresponde à allowlist local")
    expires_at = action.get("expires_at")
    if not isinstance(expires_at, str) or parse_utc(expires_at) <= datetime.now(timezone.utc):
        raise Risk3Error("exceção risco 3 expirada", EXIT_EXPIRED)
    command = action.get("command")
    if not isinstance(command, list):
        raise Risk3Error("comando allowlisted inválido")
    _guard_common(action_id, requested_scope, command, strict_secret_options=True)
    return command


def _git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


def validate_development_mode(
    config: dict[str, Any], action_id: str, requested_scope: str,
    cwd: Path, command: list[str],
) -> tuple[list[str], dict[str, str]]:
    mode = config.get("development_mode")
    if not isinstance(mode, dict) or mode.get("enabled") is not True:
        raise Risk3Error("action_id não está allowlisted localmente")
    environment = str(mode.get("environment", "")).casefold()
    if environment not in SAFE_ENVIRONMENTS:
        raise Risk3Error("modo de desenvolvimento limitado a local/dev")
    if mode.get("reason") != DEV_MODE_REASON:
        raise Risk3Error("motivo do modo de desenvolvimento inválido")
    activated_raw = mode.get("activated_at")
    expires_raw = mode.get("expires_at")
    if not isinstance(activated_raw, str) or not isinstance(expires_raw, str):
        raise Risk3Error("janela do modo de desenvolvimento inválida")
    activated_at = parse_utc(activated_raw)
    expires_at = parse_utc(expires_raw)
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise Risk3Error("modo de desenvolvimento expirado", EXIT_EXPIRED)
    if expires_at - activated_at > timedelta(days=DEV_MODE_MAX_DAYS, minutes=5):
        raise Risk3Error("modo de desenvolvimento excede limite de 30 dias")
    patterns = mode.get("allowed_roots")
    if not isinstance(patterns, list) or not patterns or not all(isinstance(item, str) and item for item in patterns):
        raise Risk3Error("modo de desenvolvimento sem allowed_roots válidos")
    if not matches_allowed_root(cwd, patterns):
        raise Risk3Error("cwd fora dos diretórios permitidos no modo de desenvolvimento")

    if not command:
        raise Risk3Error("modo de desenvolvimento exige comando explícito após --")
    exe = normalize_executable(command[0])
    configured_execs = mode.get("allowed_executables", ["python", "python3"])
    if not isinstance(configured_execs, list) or not configured_execs:
        raise Risk3Error("modo de desenvolvimento sem executáveis permitidos")
    allowed_execs = {normalize_executable(str(item)) for item in configured_execs} & DEV_EXECUTABLES
    if exe not in allowed_execs:
        raise Risk3Error("modo de desenvolvimento permite somente Python versionado")
    if len(command) < 2 or command[1].startswith("-") or not command[1].casefold().endswith(".py"):
        raise Risk3Error("modo de desenvolvimento exige caminho de script Python")

    _guard_common(action_id, requested_scope, command, strict_secret_options=False)

    cwd_resolved = cwd.resolve()
    if not cwd_resolved.is_dir():
        raise Risk3Error("cwd inexistente")
    root_result = _git(cwd_resolved, ["rev-parse", "--show-toplevel"])
    if root_result.returncode != 0 or root_result.stderr.strip():
        raise Risk3Error("modo de desenvolvimento exige repositório Git válido")
    repo_root = Path(root_result.stdout.strip()).resolve()
    if normalize_path(repo_root) != normalize_path(cwd_resolved):
        raise Risk3Error("modo de desenvolvimento exige cwd na raiz do repositório")
    status = _git(repo_root, ["status", "--porcelain", "--untracked-files=all"])
    if status.returncode != 0 or status.stderr.strip() or status.stdout.strip():
        raise Risk3Error("modo de desenvolvimento exige worktree Git limpo")

    script = Path(command[1])
    script_abs = (repo_root / script).resolve() if not script.is_absolute() else script.resolve()
    try:
        script_rel = script_abs.relative_to(repo_root)
    except ValueError as exc:
        raise Risk3Error("script fora do repositório") from exc
    if not script_abs.is_file():
        raise Risk3Error("script de desenvolvimento inexistente")
    tracked = _git(repo_root, ["ls-files", "--error-unmatch", script_rel.as_posix()])
    if tracked.returncode != 0:
        raise Risk3Error("script de desenvolvimento deve estar versionado")
    head = _git(repo_root, ["rev-parse", "HEAD"])
    if head.returncode != 0 or head.stderr.strip() or not head.stdout.strip():
        raise Risk3Error("não foi possível resolver HEAD do repositório")
    return command, {
        "execution_mode": "development_mode",
        "environment": environment,
        "git_head": head.stdout.strip(),
        "script_path_sha256": hashlib.sha256(script_rel.as_posix().encode("utf-8")).hexdigest(),
        "script_sha256": sha256_file(script_abs),
        "development_reason": DEV_MODE_REASON,
        "development_expires_at": expires_at.isoformat(),
    }


def append_audit(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "risk3-audit.jsonl"
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def execute_action(
    *, config_path: Path, action_id: str, scope: str, cwd: Path,
    timeout: int, correlation_id: str, command_override: list[str] | None = None,
) -> int:
    config = load_local_config(config_path)
    actions = config.get("actions")
    action = actions.get(action_id) if isinstance(actions, dict) else None
    if isinstance(action, dict):
        if command_override:
            raise Risk3Error("ação allowlisted não aceita comando ad-hoc")
        command = validate_action(action_id, scope, action)
        audit_mode = {
            "execution_mode": "explicit_allowlist",
            "environment": str(action.get("environment", "")).casefold(),
        }
    else:
        command, audit_mode = validate_development_mode(
            config, action_id, scope, cwd, command_override or [],
        )
    if timeout < 1 or timeout > 900:
        raise Risk3Error("timeout fora do limite 1..900s")
    if not cwd.is_dir():
        raise Risk3Error("cwd inexistente")

    started = utc_now()
    audit_base = {
        "schema_version": "1.1.0",
        "event": "owner_risk3_execution",
        "correlation_id": correlation_id,
        "action_id": action_id,
        **audit_mode,
        "owner_fingerprint_hash": hashlib.sha256(owner_fingerprint().encode("ascii")).hexdigest(),
        "scope_sha256": hashlib.sha256(scope.encode("utf-8")).hexdigest(),
        "command_sha256": sha256_json(command),
        "started_at": started,
    }
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), shell=False, text=True,
            capture_output=True, timeout=timeout, check=False,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        append_audit(default_state_dir(), {**audit_base, "finished_at": utc_now(), "result": "timeout"})
        raise Risk3Error("execução risco 3 excedeu timeout", EXIT_TIMEOUT) from exc

    append_audit(default_state_dir(), {
        **audit_base,
        "finished_at": utc_now(),
        "result": "success" if completed.returncode == 0 else "command_failed",
        "returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8", errors="replace")).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8", errors="replace")).hexdigest(),
    })
    if completed.returncode != 0:
        raise Risk3Error(f"comando governado falhou com exit={completed.returncode}", EXIT_COMMAND)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exceção local auditável para ações Risk 3 do proprietário")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--action-id")
    parser.add_argument("--scope")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--correlation-id", default=None)
    parser.add_argument("--print-owner-fingerprint", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    ns = build_parser().parse_args()
    if ns.print_owner_fingerprint:
        print(owner_fingerprint())
        return 0
    if not ns.action_id or not ns.scope:
        print(json.dumps({"status": "blocked", "reason": "--action-id e --scope são obrigatórios"}), file=sys.stderr)
        return EXIT_POLICY
    command = list(ns.command)
    if command and command[0] == "--":
        command = command[1:]
    correlation_id = ns.correlation_id or str(uuid.uuid4())
    try:
        return execute_action(
            config_path=ns.config.expanduser(), action_id=ns.action_id,
            scope=ns.scope, cwd=ns.cwd.resolve(), timeout=ns.timeout,
            correlation_id=correlation_id, command_override=command,
        )
    except Risk3Error as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "correlation_id": correlation_id}), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
