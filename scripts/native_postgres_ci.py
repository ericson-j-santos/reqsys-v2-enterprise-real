#!/usr/bin/env python3
"""Disposable PostgreSQL 16 fixture for GitHub-hosted Ubuntu 24.04 CI.

Uses only the image's versioned binaries. No sudo, package installation,
system service, Docker, existing cluster or SQLite fallback is permitted.
The state file contains ownership metadata, never a database password.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

BIN = Path("/usr/lib/postgresql/16/bin")
TOOLS = ("postgres", "initdb", "pg_ctl", "pg_isready", "psql")
USER = "reqsys_app"
DATABASE = "reqsys_test"
CONTEXT_KEYS = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "GITHUB_SHA")
VERSION_RE = re.compile(r"\(PostgreSQL\)\s+(16(?:\.\d+)*)(?:\s|$)")
RECEIPT_FIELDS = frozenset({"status", "select_1", "server_version_num",
                            "authentication", "cleanup", "independent_read",
                            "wrong_password_rejected",
                            "stopped_pg_isready_exit", "stopped_psql_exit",
                            "stopped_probe_rejected", "restart_persistence"})


class FixtureError(RuntimeError):
    """Only fixed, non-secret diagnostic codes are exposed by the CLI."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FixtureError(code)


def context() -> dict[str, str]:
    values = {key: os.environ.get(key, "") for key in CONTEXT_KEYS}
    require(all(values.values()), "missing_ci_context")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", values["GITHUB_SHA"])), "invalid_sha")
    require(values["GITHUB_RUN_ID"].isdigit(), "invalid_run_id")
    require(values["GITHUB_RUN_ATTEMPT"].isdigit(), "invalid_run_attempt")
    return values


def require_runtime() -> Path:
    require(sys.platform == "linux", "linux_required")
    require(os.geteuid() != 0, "non_root_required")
    require(os.environ.get("GITHUB_ACTIONS") == "true", "github_actions_required")
    release = Path("/etc/os-release").read_text(encoding="utf-8")
    require('ID=ubuntu\n' in release and 'VERSION_ID="24.04"' in release,
            "ubuntu_24_04_required")
    context()
    raw = os.environ.get("RUNNER_TEMP", "")
    require(bool(raw) and "\n" not in raw and "|" not in raw, "invalid_runner_temp")
    path = Path(raw)
    require(path.is_absolute() and path.is_dir() and not path.is_symlink(),
            "invalid_runner_temp")
    return path.resolve()


def private_file(path: Path, value: str, *, exclusive: bool = True) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(value)


def private_owned(path: Path, *, directory: bool = False) -> None:
    info = path.lstat()
    require(info.st_uid == os.geteuid(), "foreign_owner")
    require(not stat.S_ISLNK(info.st_mode), "symlink_forbidden")
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
            "invalid_file_type")
    require(stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o600),
            "private_permissions_required")


def command(tool: str, args: list[str], *, env: dict[str, str] | None = None,
            check: bool = True, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    require(tool in TOOLS, "tool_not_allowed")
    clean_env = {k: v for k, v in os.environ.items()
                 if not k.startswith("PG") and k != "DATABASE_URL"}
    clean_env["LC_ALL"] = "C"
    clean_env["PGCONNECT_TIMEOUT"] = "5"
    if env:
        clean_env.update(env)
    try:
        result = subprocess.run([str(BIN / tool), *args], env=clean_env,
                                stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FixtureError(f"{tool}_unavailable_or_timeout") from exc
    if check and result.returncode != 0:
        raise FixtureError(f"{tool}_failed_exit_{result.returncode}")
    return result


def verify_binaries() -> dict[str, str]:
    versions = {}
    for tool in TOOLS:
        binary = BIN / tool
        info = binary.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0,
                "official_image_binary_required")
        require(not info.st_mode & 0o022 and os.access(binary, os.X_OK),
                "unsafe_binary_permissions")
        match = VERSION_RE.search(command(tool, ["--version"]).stdout)
        require(match is not None, "postgresql_major_16_required")
        versions[tool] = match.group(1)
    require(len(set(versions.values())) == 1, "mixed_postgresql_toolchain")
    return versions


def free_port() -> int:
    # Port allocation has an unavoidable bind/start race; startup fails closed
    # on collision and never kills, reuses or changes the competing listener.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def paths(state: dict) -> tuple[Path, Path, Path]:
    root = Path(state["root"])
    return root, root / "data", root / "socket"


def receipt_path() -> Path:
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    directory = workspace / "artifacts" / "native-postgres"
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.resolve() == directory, "receipt_symlink_forbidden")
    return directory / "receipt.json"


def receipt(state: dict, **updates: object) -> None:
    path = receipt_path()
    payload = {
        "schema_version": "1.0", "fixture": "native-postgresql-16",
        "context": state["context"], "instance_id": state["instance_id"],
        "runner_image": os.environ.get("ImageVersion", "unknown"),
        "tool_versions": state["versions"], "host": "127.0.0.1",
        "port": state["port"], "status": "initializing",
    }
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        require(previous.get("instance_id") == state["instance_id"]
                and previous.get("context") == state["context"],
                "stale_receipt_forbidden")
        payload.update({key: value for key, value in previous.items() if key in RECEIPT_FIELDS})
    require(set(updates) <= RECEIPT_FIELDS, "receipt_field_not_allowed")
    payload.update(updates)
    # Only explicitly selected fields are written. No raw commands, environment,
    # stdout/stderr, connection string, filesystem state or password is copied.
    private_file(path, json.dumps(payload, indent=2) + "\n", exclusive=not path.exists())


def load_state(state_path: Path) -> dict | None:
    temp = require_runtime()
    require(state_path.is_absolute() and state_path.parent.resolve() == temp,
            "state_outside_runner_temp")
    if not state_path.exists():
        require(not state_path.is_symlink(), "symlink_forbidden")
        return None
    private_owned(state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    require(state.get("context") == context() and state.get("uid") == os.geteuid(),
            "foreign_ci_context")
    root, data, sock = paths(state)
    require(root.parent == temp and root.name.startswith("reqsys-pg16-"),
            "foreign_cluster_path")
    require(root.resolve() == root, "symlink_forbidden")
    private_owned(root, directory=True)
    marker = root / "owner.json"
    private_owned(marker)
    require(json.loads(marker.read_text(encoding="utf-8")) == state,
            "ownership_marker_mismatch")
    for child in (data, sock):
        if child.exists() or child.is_symlink():
            private_owned(child, directory=True)
    require(Path(state["state_path"]) == state_path, "state_path_mismatch")
    env_file = Path(state["env_file"])
    require(env_file.parent == temp, "env_outside_runner_temp")
    if env_file.exists() or env_file.is_symlink():
        private_owned(env_file)
    return state


def sql(state: dict, query: str, *, database: str = DATABASE,
        check: bool = True, passfile: Path | None = None) -> subprocess.CompletedProcess[str]:
    root, _, _ = paths(state)
    passfile = passfile if passfile is not None else root / "pgpass"
    require(passfile.parent == root and passfile.name in ("pgpass", "wrong-pgpass"),
            "foreign_passfile_forbidden")
    private_owned(passfile)
    return command("psql", ["-X", "-w", "-A", "-t", "-v", "ON_ERROR_STOP=1",
                            "-h", "127.0.0.1", "-p", str(state["port"]),
                            "-U", USER, "-d", database, "-c", query],
                   env={"PGPASSFILE": str(passfile)}, check=check)


def is_ready(state: dict) -> int:
    return command("pg_isready", ["-h", "127.0.0.1", "-p", str(state["port"]),
                                  "-U", USER, "-d", DATABASE, "-t", "5"],
                   check=False).returncode


def probe(state: dict) -> int:
    require(is_ready(state) == 0, "postgres_not_ready")
    result = sql(state, "SELECT current_setting('data_directory'), "
                 "current_setting('server_version_num'), 1, inet_server_addr(), "
                 "inet_server_port(), current_user, current_database();")
    fields = result.stdout.strip().split("|")
    _, data, _ = paths(state)
    require(len(fields) == 7 and fields[0] == str(data) and fields[2] == "1"
            and fields[3:] == ["127.0.0.1", str(state["port"]), USER, DATABASE],
            "server_identity_mismatch")
    require(fields[1].isdigit() and 160000 <= int(fields[1]) < 170000,
            "server_major_16_required")
    require(sql(state, "SELECT rolpassword LIKE 'SCRAM-SHA-256$%' "
                "FROM pg_authid WHERE rolname = current_user;").stdout.strip() == "t",
            "scram_verifier_required")
    return int(fields[1])


def start_server(state: dict) -> None:
    root, data, _ = paths(state)
    command("pg_ctl", ["-D", str(data), "-l", str(root / "postgres.log"),
                       "-w", "-t", "30", "start"])


def stop_server(state: dict) -> None:
    _, data, _ = paths(state)
    pidfile = data / "postmaster.pid"
    if not pidfile.exists():
        return
    private_owned(pidfile)
    lines = pidfile.read_text(encoding="utf-8").splitlines()
    require(len(lines) >= 4 and lines[0].isdigit() and lines[1] == str(data)
            and lines[3] == str(state["port"]), "postmaster_identity_mismatch")
    proc = Path("/proc") / lines[0]
    if not proc.exists():
        return
    require(proc.stat().st_uid == os.geteuid(), "foreign_postmaster_owner")
    require((proc / "exe").resolve() == BIN / "postgres", "foreign_postmaster_binary")
    argv = (proc / "cmdline").read_bytes().split(b"\0")
    require(b"-D" in argv and argv[argv.index(b"-D") + 1] == os.fsencode(data),
            "foreign_postmaster_datadir")
    command("pg_ctl", ["-D", str(data), "-m", "fast", "-w", "-t", "30", "stop"])
    require(not pidfile.exists(), "postmaster_still_running")


def create(state_path: Path, env_file: Path) -> None:
    temp = require_runtime()
    require(state_path.parent.resolve() == temp and env_file.parent.resolve() == temp,
            "output_outside_runner_temp")
    require(state_path.is_absolute() and env_file.is_absolute() and state_path != env_file,
            "invalid_output_paths")
    require(not state_path.exists() and not state_path.is_symlink(), "state_already_exists")
    require(not env_file.exists() and not env_file.is_symlink(), "env_already_exists")
    versions = verify_binaries()
    root = Path(tempfile.mkdtemp(prefix="reqsys-pg16-", dir=temp))
    root.chmod(0o700)
    state = {"schema_version": "1.0", "root": str(root), "uid": os.geteuid(),
             "context": context(), "instance_id": secrets.token_hex(16),
             "port": free_port(), "versions": versions,
             "state_path": str(state_path), "env_file": str(env_file)}
    encoded = json.dumps(state, sort_keys=True) + "\n"
    private_file(root / "owner.json", encoded)
    private_file(state_path, encoded)
    try:
        receipt(state)
        _, data, sock = paths(state)
        sock.mkdir(mode=0o700)
        require(len(os.fsencode(sock)) + 20 < 108, "unix_socket_path_too_long")
        password = secrets.token_hex(32)
        print("::add-mask::" + password, flush=True)
        private_file(root / "init-password", password + "\n")
        private_file(root / "pgpass", f"127.0.0.1:{state['port']}:*:{USER}:{password}\n")
        del password
        command("initdb", ["-D", str(data), "-U", USER, "--encoding=UTF8",
                           "--locale=C", "--auth-local=scram-sha-256",
                           "--auth-host=scram-sha-256", "--pwfile=" + str(root / "init-password")],
                timeout=90)
        (root / "init-password").unlink()
        private_file(data / "pg_hba.conf", "local all all scram-sha-256\n"
                     "host all all 127.0.0.1/32 scram-sha-256\n", exclusive=False)
        quoted_socket = str(sock).replace("'", "''")
        config = ("listen_addresses = '127.0.0.1'\n"
                  f"port = {state['port']}\n"
                  f"unix_socket_directories = '{quoted_socket}'\n"
                  "unix_socket_permissions = 0700\n"
                  "password_encryption = 'scram-sha-256'\n"
                  "log_statement = 'none'\n"
                  "log_min_error_statement = 'panic'\n")
        with (data / "postgresql.conf").open("a", encoding="utf-8") as stream:
            stream.write("\n" + config)
        start_server(state)
        sql(state, f"CREATE DATABASE {DATABASE};", database="postgres")
        version_num = probe(state)
        url = f"postgresql+psycopg2://{USER}@127.0.0.1:{state['port']}/{DATABASE}?connect_timeout=5"
        exports = {"DATABASE_URL": url, "PGPASSFILE": str(root / "pgpass")}
        private_file(env_file, "".join(f"export {key}={shlex.quote(value)}\n"
                                       for key, value in exports.items()))
        receipt(state, status="ready", select_1=True, server_version_num=version_num,
                authentication="scram-sha-256", cleanup="pending")
    except BaseException:
        cleanup(state_path)
        raise


def reject_wrong_password(state: dict) -> None:
    root, _, _ = paths(state)
    wrong_passfile = root / "wrong-pgpass"
    private_file(wrong_passfile, f"127.0.0.1:{state['port']}:*:{USER}:{secrets.token_hex(32)}\n")
    try:
        result = sql(state, "SELECT 1;", check=False, passfile=wrong_passfile)
        require(result.returncode == 2 and "password authentication failed" in result.stderr,
                "wrong_password_negative_failed")
    finally:
        wrong_passfile.unlink(missing_ok=True)


def exercise(state: dict) -> None:
    version_num = probe(state)
    reject_wrong_password(state)
    marker = secrets.token_hex(16)
    sql(state, "CREATE TABLE public.reqsys_native_ci_probe (marker text PRIMARY KEY);")
    sql(state, f"INSERT INTO public.reqsys_native_ci_probe VALUES ('{marker}');")
    query = "SELECT marker FROM public.reqsys_native_ci_probe;"
    require(sql(state, query).stdout.strip() == marker, "independent_read_failed")
    stop_server(state)
    ready_exit = is_ready(state)
    sql_exit = sql(state, "SELECT 1;", check=False).returncode
    require(ready_exit == 2 and sql_exit == 2, "stopped_database_negative_failed")
    try:
        probe(state)
    except FixtureError as exc:
        require(str(exc) == "postgres_not_ready", "unexpected_negative_failure")
    else:
        raise FixtureError("stopped_probe_false_green")
    start_server(state)
    require(probe(state) == version_num, "restart_version_changed")
    require(sql(state, query).stdout.strip() == marker, "restart_persistence_failed")
    sql(state, "DROP TABLE public.reqsys_native_ci_probe;")
    receipt(state, status="exercised", independent_read=True,
            wrong_password_rejected=True,
            stopped_pg_isready_exit=ready_exit, stopped_psql_exit=sql_exit,
            stopped_probe_rejected=True, restart_persistence=True)


def cleanup(state_path: Path) -> None:
    state = load_state(state_path)
    if state is None:
        return
    try:
        stop_server(state)
        require(is_ready(state) == 2, "cleanup_listener_not_absent")
    except (FixtureError, OSError, ValueError, KeyError, IndexError):
        try:
            receipt(state, cleanup="blocked")
        except (FixtureError, OSError, ValueError, KeyError, IndexError):
            pass  # Preserve the original error and the private state for always.
        raise
    root, _, _ = paths(state)
    # The complete ownership validation above precedes any recursive deletion.
    # No user-supplied PGDATA, system service, global PID, or port is stopped.
    shutil.rmtree(root)
    Path(state["env_file"]).unlink(missing_ok=True)
    state_path.unlink()
    receipt(state, cleanup="passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "probe", "exercise", "cleanup"))
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "start":
            require(args.env_file is not None, "env_file_required")
            create(args.state, args.env_file)
        elif args.action == "cleanup":
            cleanup(args.state)
        else:
            state = load_state(args.state)
            require(state is not None, "state_missing")
            if args.action == "probe":
                probe(state)
            else:
                exercise(state)
    except FixtureError as exc:
        print(f"NATIVE_POSTGRES_BLOCKED:{exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, IndexError):
        print("NATIVE_POSTGRES_BLOCKED:invalid_or_unavailable_fixture_state", file=sys.stderr)
        return 1
    print(f"NATIVE_POSTGRES_{args.action.upper()}_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
