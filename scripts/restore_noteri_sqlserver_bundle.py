"""Restore the verified NOTERI SQL Server backup set on the final desktop.

This command is intentionally bound to one host, one extracted bundle, one
container name, and one pinned Microsoft SQL Server image digest.  It never
accepts a password on the command line and emits only a sanitized JSON result.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import socket
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

TARGET_HOST = "DESKTOP-PDQK954"
SOURCE_HOST = "NOTERI"
MANIFEST_SCHEMA = "reqsys-noteri-sqlserver-backup-set-v1"
RESULT_SCHEMA = "reqsys-noteri-sqlserver-restore-result-v1"
CONTAINER_SCHEMA = "reqsys-noteri-sqlserver-container-v1"
CONTAINER_NAME = "reqsys-noteri-migration-sql2025"
VOLUME_NAME = "reqsys-noteri-migration-sql2025-data"
IMAGE_NAME = "mcr.microsoft.com/mssql/server:2025-latest"
IMAGE_DIGEST = "sha256:2b5b581621126574f3d1f75e78d3eebe8d05aedb59ad0cfdf9aa42cb0634d726"
IMAGE_REF = f"{IMAGE_NAME}@{IMAGE_DIGEST}"
BACKUP_MOUNT = "/backups/noteri"
DATA_MOUNT = "/var/opt/mssql"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
CONFIRMATION = "RESTORE-NOTERI-SQLSERVER-BUNDLE"

SYSTEM_DATABASES = frozenset({"master", "model", "msdb"})
EXPECTED_DATABASES = frozenset(
    {
        "AdventureWorks2025",
        "ChatGPT_SQL_JSON_Practice_20260920_001",
        "lab",
        "master",
        "model",
        "msdb",
        "mvp_intelligence",
        "PentahoLab",
        "ReportServer",
        "ReportServerTempDB",
        "reqsys",
        "ReqSysIntegrationDev",
        "ReqSysMovimentoCorporateValidationDev",
        "ReqSysMovimentoDev",
        "ReqSysMovimentoOwnerDev",
        "ReqSysMovimentoSourceDev",
        "teams",
    }
)
USER_DATABASES = frozenset(EXPECTED_DATABASES - SYSTEM_DATABASES)
MANIFEST_FIELDS = {
    "schema",
    "source_host",
    "created_at_local",
    "backup_options",
    "restore_verifyonly",
    "database_count",
    "files",
}
FILE_FIELDS = {"name", "bytes", "sha256"}
SAFE_BACKUP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\.bak")
SAFE_LOGICAL_NAME = re.compile(r"[A-Za-z0-9_ .#$@()\-]{1,128}")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")


class RestoreError(RuntimeError):
    """Stable, non-sensitive restore failure."""


def reject(code: str) -> None:
    raise RestoreError(code)


def sql_string(value: str) -> str:
    """Quote an arbitrary value as a Unicode T-SQL string literal."""
    if "\x00" in value or "\r" in value or "\n" in value:
        reject("unsafe_sql_string")
    return "N'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    """Quote an arbitrary SQL Server identifier."""
    if not value or "\x00" in value or "\r" in value or "\n" in value:
        reject("unsafe_sql_identifier")
    return "[" + value.replace("]", "]]") + "]"


def database_from_backup_name(name: str) -> str:
    if not isinstance(name, str) or not SAFE_BACKUP_NAME.fullmatch(name):
        reject("invalid_backup_name")
    path = Path(name)
    if path.name != name or path.suffix.casefold() != ".bak":
        reject("invalid_backup_name")
    return path.stem


def select_user_databases(database_names: list[str]) -> list[str]:
    if len(database_names) != 17 or len(set(database_names)) != 17:
        reject("unexpected_database_inventory")
    if frozenset(database_names) != EXPECTED_DATABASES:
        reject("unexpected_database_inventory")
    selected = sorted(
        (name for name in database_names if name not in SYSTEM_DATABASES),
        key=str.casefold,
    )
    if len(selected) != 14 or frozenset(selected) != USER_DATABASES:
        reject("unexpected_user_database_inventory")
    return selected


def parse_manifest(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != MANIFEST_FIELDS:
        reject("invalid_manifest_shape")
    if value.get("schema") != MANIFEST_SCHEMA:
        reject("invalid_manifest_schema")
    if value.get("source_host") != SOURCE_HOST:
        reject("invalid_manifest_source")
    if value.get("created_at_local") != "2026-10-07T07:15:03-03:00":
        reject("invalid_manifest_creation_time")
    if value.get("database_count") != 17 or value.get("restore_verifyonly") is not True:
        reject("invalid_manifest_verification")
    options = value.get("backup_options")
    if (
        not isinstance(options, list)
        or not options
        or not all(isinstance(option, str) and option for option in options)
        or len(options) != len(set(options))
    ):
        reject("invalid_manifest_backup_options")
    files = value.get("files")
    if not isinstance(files, list) or len(files) != 17:
        reject("invalid_manifest_file_count")

    normalized: list[dict[str, Any]] = []
    names: list[str] = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != FILE_FIELDS:
            reject("invalid_manifest_file_entry")
        name = entry.get("name")
        size = entry.get("bytes")
        digest = entry.get("sha256")
        database = database_from_backup_name(name)
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            reject("invalid_manifest_file_size")
        if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
            reject("invalid_manifest_file_digest")
        names.append(database)
        normalized.append(
            {"name": name, "database": database, "bytes": size, "sha256": digest}
        )
    select_user_databases(names)
    if len({entry["name"].casefold() for entry in normalized}) != 17:
        reject("duplicate_backup_name")
    return normalized


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(block)
    except OSError:
        reject("backup_file_unreadable")
    return digest.hexdigest()


def verify_bundle(bundle_dir: Path) -> list[dict[str, Any]]:
    try:
        root = bundle_dir.resolve(strict=True)
        root_stat = root.stat(follow_symlinks=False)
    except OSError:
        reject("bundle_directory_unavailable")
    if not stat.S_ISDIR(root_stat.st_mode) or _is_reparse(root_stat):
        reject("bundle_directory_invalid")
    manifest_path = root / "manifest.json"
    try:
        manifest_stat = manifest_path.stat(follow_symlinks=False)
        if not stat.S_ISREG(manifest_stat.st_mode) or _is_reparse(manifest_stat):
            reject("manifest_file_invalid")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except RestoreError:
        raise
    except (OSError, UnicodeError, ValueError):
        reject("manifest_file_invalid")
    files = parse_manifest(manifest)
    expected_entries = {"manifest.json", *(entry["name"] for entry in files)}
    try:
        observed_entries = {entry.name for entry in root.iterdir()}
    except OSError:
        reject("bundle_directory_unreadable")
    if observed_entries != expected_entries:
        reject("unexpected_bundle_entry")

    for entry in files:
        path = root / entry["name"]
        try:
            metadata = path.stat(follow_symlinks=False)
        except OSError:
            reject("backup_file_unavailable")
        if (
            not stat.S_ISREG(metadata.st_mode)
            or _is_reparse(metadata)
            or metadata.st_nlink != 1
            or metadata.st_size != entry["bytes"]
        ):
            reject("backup_file_metadata_mismatch")
        if not hmac.compare_digest(sha256_file(path), entry["sha256"]):
            reject("backup_file_digest_mismatch")
    return files


def _is_reparse(metadata: os.stat_result) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def validate_password(password: str | None) -> str:
    if (
        not isinstance(password, str)
        or not 16 <= len(password) <= 128
        or any(character in password for character in "\x00\r\n")
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"[0-9]", password)
        or not re.search(r"[^A-Za-z0-9]", password)
    ):
        reject("strong_sa_password_required")
    return password


def _docker(
    arguments: list[str],
    *,
    code: str,
    extra_env: dict[str, str] | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if extra_env:
        environment.update(extra_env)
    try:
        result = subprocess.run(
            ["docker", *arguments],
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            env=environment,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        reject(code)
    if result.returncode != 0 and not allow_failure:
        reject(code)
    return result


def _json_list(output: str, code: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(output)
    except (TypeError, ValueError):
        reject(code)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        reject(code)
    return value


def inspect_named(kind: str, name: str) -> dict[str, Any] | None:
    if kind == "container":
        inventory_arguments = [
            "container",
            "ls",
            "--all",
            "--filter",
            f"name=^{name}$",
            "--format",
            "{{.Names}}",
        ]
    elif kind == "volume":
        inventory_arguments = [
            "volume",
            "ls",
            "--filter",
            f"name=^{name}$",
            "--format",
            "{{.Name}}",
        ]
    else:
        reject("unsupported_docker_resource_kind")
    result = _docker(
        [kind, "inspect", name], code=f"{kind}_inspect_failed", allow_failure=True
    )
    if result.returncode != 0:
        listed = _docker(
            inventory_arguments,
            code=f"{kind}_inventory_failed",
        )
        if listed.stdout.strip():
            reject(f"{kind}_inspect_failed")
        return None
    return _json_list(result.stdout, f"invalid_{kind}_inspect")[0]


def prepare_image() -> dict[str, Any]:
    _docker(
        ["info", "--format", "{{json .ServerVersion}}"],
        code="docker_daemon_unavailable",
    )
    _docker(["pull", "--quiet", IMAGE_REF], code="pinned_image_pull_failed")
    inspected = _docker(
        ["image", "inspect", IMAGE_REF], code="pinned_image_inspect_failed"
    )
    image = _json_list(inspected.stdout, "invalid_image_inspect")[0]
    image_id = image.get("Id")
    digests = image.get("RepoDigests")
    if (
        not isinstance(image_id, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
        or not isinstance(digests, list)
        or not any(
            isinstance(value, str) and value.endswith("@" + IMAGE_DIGEST)
            for value in digests
        )
    ):
        reject("pinned_image_digest_mismatch")
    return {"id": image_id, "digest": IMAGE_DIGEST}


def _resource_labels() -> dict[str, str]:
    return {
        "com.reqsys.migration.schema": CONTAINER_SCHEMA,
        "com.reqsys.migration.source": SOURCE_HOST,
        "com.reqsys.migration.target": TARGET_HOST,
        "com.reqsys.migration.image-digest": IMAGE_DIGEST,
    }


def prepare_volume() -> None:
    expected = _resource_labels()
    volume = inspect_named("volume", VOLUME_NAME)
    if volume is None:
        arguments = ["volume", "create", "--driver", "local"]
        for name, value in expected.items():
            arguments.extend(["--label", f"{name}={value}"])
        arguments.append(VOLUME_NAME)
        created = _docker(arguments, code="volume_create_failed")
        if created.stdout.strip() != VOLUME_NAME:
            reject("unexpected_volume_create_output")
        volume = inspect_named("volume", VOLUME_NAME)
    if (
        not isinstance(volume, dict)
        or volume.get("Name") != VOLUME_NAME
        or volume.get("Driver") != "local"
        or volume.get("Scope") != "local"
        or (volume.get("Options") not in (None, {}))
        or volume.get("Labels") != expected
    ):
        reject("incompatible_existing_volume")


def _mount_by_destination(container: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mounts = container.get("Mounts")
    if not isinstance(mounts, list):
        reject("invalid_container_mounts")
    result: dict[str, dict[str, Any]] = {}
    for mount in mounts:
        if not isinstance(mount, dict) or not isinstance(mount.get("Destination"), str):
            reject("invalid_container_mounts")
        result[mount["Destination"]] = mount
    if len(result) != len(mounts):
        reject("invalid_container_mounts")
    return result


def _same_path(left: str, right: Path) -> bool:
    try:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
            str(right.resolve())
        )
    except OSError:
        return False


def validate_container(
    container: dict[str, Any], bundle_dir: Path, image_id: str, password: str
) -> str:
    config = container.get("Config")
    host_config = container.get("HostConfig")
    state = container.get("State")
    if not all(isinstance(value, dict) for value in (config, host_config, state)):
        reject("incompatible_existing_container")
    labels = config.get("Labels")
    if not isinstance(labels, dict) or any(
        labels.get(name) != value for name, value in _resource_labels().items()
    ):
        reject("incompatible_existing_container")
    environment = config.get("Env")
    if not isinstance(environment, list) or not all(
        isinstance(item, str) for item in environment
    ):
        reject("incompatible_existing_container")
    env_map = dict(item.split("=", 1) for item in environment if "=" in item)
    if (
        container.get("Name") != "/" + CONTAINER_NAME
        or container.get("Image") != image_id
        or config.get("Image") != IMAGE_REF
        or env_map.get("ACCEPT_EULA") != "Y"
        or env_map.get("MSSQL_PID") != "Developer"
        or not hmac.compare_digest(env_map.get("MSSQL_SA_PASSWORD", ""), password)
        or host_config.get("NetworkMode") != "none"
        or host_config.get("PortBindings") not in (None, {})
        or (host_config.get("RestartPolicy") or {}).get("Name", "no") != "no"
    ):
        reject("incompatible_existing_container")
    mounts = _mount_by_destination(container)
    if set(mounts) != {DATA_MOUNT, BACKUP_MOUNT}:
        reject("incompatible_existing_container")
    data_mount = mounts[DATA_MOUNT]
    backup_mount = mounts[BACKUP_MOUNT]
    if (
        data_mount.get("Type") != "volume"
        or data_mount.get("Name") != VOLUME_NAME
        or data_mount.get("RW") is not True
        or backup_mount.get("Type") != "bind"
        or backup_mount.get("RW") is not False
        or not isinstance(backup_mount.get("Source"), str)
        or not _same_path(backup_mount["Source"], bundle_dir)
    ):
        reject("incompatible_existing_container")
    status = state.get("Status")
    if status not in {"created", "exited", "running"}:
        reject("incompatible_existing_container_state")
    return status


def prepare_container(bundle_dir: Path, image_id: str, password: str) -> None:
    container = inspect_named("container", CONTAINER_NAME)
    if container is None:
        arguments = [
            "container",
            "create",
            "--name",
            CONTAINER_NAME,
            "--hostname",
            CONTAINER_NAME,
            "--network",
            "none",
            "--restart",
            "no",
        ]
        for name, value in _resource_labels().items():
            arguments.extend(["--label", f"{name}={value}"])
        arguments.extend(
            [
                "--env",
                "ACCEPT_EULA=Y",
                "--env",
                "MSSQL_PID=Developer",
                "--env",
                "MSSQL_SA_PASSWORD",
                "--mount",
                f"type=volume,src={VOLUME_NAME},dst={DATA_MOUNT}",
                "--mount",
                f"type=bind,src={bundle_dir.resolve()},dst={BACKUP_MOUNT},readonly",
                IMAGE_REF,
            ]
        )
        created = _docker(arguments, code="container_create_failed")
        if not re.fullmatch(r"[0-9a-f]{64}\s*", created.stdout):
            reject("unexpected_container_create_output")
        container = inspect_named("container", CONTAINER_NAME)
    status = validate_container(container, bundle_dir, image_id, password)
    if status != "running":
        started = _docker(
            ["container", "start", CONTAINER_NAME], code="container_start_failed"
        )
        if started.stdout.strip() != CONTAINER_NAME:
            reject("unexpected_container_start_output")


def _sqlcmd(query: str, password: str, *, code: str) -> list[str]:
    result = _docker(
        [
            "exec",
            "--env",
            "SQLCMDPASSWORD",
            CONTAINER_NAME,
            SQLCMD,
            "-S",
            "localhost",
            "-U",
            "sa",
            "-C",
            "-b",
            "-V",
            "11",
            "-l",
            "60",
            "-h",
            "-1",
            "-W",
            "-w",
            "65535",
            "-s",
            "|",
            "-Q",
            "SET NOCOUNT ON; " + query,
        ],
        code=code,
        extra_env={"SQLCMDPASSWORD": password},
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def wait_for_sql(password: str) -> str:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            output = _sqlcmd(
                "SELECT CONVERT(varchar(10), SERVERPROPERTY('ProductMajorVersion'));",
                password,
                code="sql_not_ready",
            )
            if output == ["17"]:
                return output[0]
            if output:
                reject("unexpected_sql_server_version")
        except RestoreError as exc:
            if str(exc) != "sql_not_ready":
                raise
        time.sleep(2)
    reject("sql_server_readiness_timeout")


def parse_filelistonly(lines: list[str]) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for line in lines:
        columns = line.split("|")
        if len(columns) != 22:
            reject("unexpected_filelistonly_output")
        logical_name = columns[0].strip()
        file_type = columns[2].strip()
        if not SAFE_LOGICAL_NAME.fullmatch(logical_name) or file_type not in {"D", "L"}:
            reject("unexpected_filelistonly_output")
        files.append((logical_name, file_type))
    if (
        not files
        or len(files) > 32
        or len({name.casefold() for name, _ in files}) != len(files)
        or not any(file_type == "D" for _, file_type in files)
        or not any(file_type == "L" for _, file_type in files)
    ):
        reject("unexpected_filelistonly_output")
    return files


def safe_move_targets(
    database: str, files: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    slug = re.sub(r"[^a-z0-9]+", "_", database.casefold()).strip("_")
    if not slug:
        reject("unsafe_move_target")
    data_number = 0
    log_number = 0
    targets: list[tuple[str, str]] = []
    for logical_name, file_type in files:
        if file_type == "D":
            data_number += 1
            extension = "mdf" if data_number == 1 else "ndf"
            ordinal = data_number
        elif file_type == "L":
            log_number += 1
            extension = "ldf"
            ordinal = log_number
        else:
            reject("unsafe_move_target")
        target = f"/var/opt/mssql/data/noteri_{slug}_{ordinal}.{extension}"
        targets.append((logical_name, target))
    if len({target for _, target in targets}) != len(targets):
        reject("unsafe_move_target")
    return targets


def _expect_absent(database: str, password: str) -> None:
    output = _sqlcmd(
        f"SELECT CASE WHEN DB_ID({sql_string(database)}) IS NULL THEN 'ABSENT' ELSE 'PRESENT' END;",
        password,
        code="database_presence_check_failed",
    )
    if output != ["ABSENT"]:
        reject("target_database_already_exists")


def restore_database(entry: dict[str, Any], password: str) -> None:
    database = entry["database"]
    backup_path = f"{BACKUP_MOUNT}/{entry['name']}"
    _expect_absent(database, password)
    filelist = _sqlcmd(
        f"RESTORE FILELISTONLY FROM DISK = {sql_string(backup_path)};",
        password,
        code="restore_filelistonly_failed",
    )
    moves = safe_move_targets(database, parse_filelistonly(filelist))
    _sqlcmd(
        f"RESTORE VERIFYONLY FROM DISK = {sql_string(backup_path)} WITH CHECKSUM;",
        password,
        code="restore_verifyonly_failed",
    )
    move_sql = ", ".join(
        f"MOVE {sql_string(logical)} TO {sql_string(target)}"
        for logical, target in moves
    )
    query = (
        f"IF DB_ID({sql_string(database)}) IS NOT NULL THROW 51001, "
        "'TARGET_DATABASE_ALREADY_EXISTS', 1; "
        f"RESTORE DATABASE {sql_identifier(database)} FROM DISK = {sql_string(backup_path)} "
        f"WITH {move_sql}, CHECKSUM, RECOVERY;"
    )
    _sqlcmd(query, password, code="database_restore_failed")
    checked = _sqlcmd(
        f"DBCC CHECKDB ({sql_identifier(database)}) WITH PHYSICAL_ONLY, NO_INFOMSGS; SELECT 'OK';",
        password,
        code="database_checkdb_failed",
    )
    if checked != ["OK"]:
        reject("unexpected_checkdb_output")


def exact_bundle_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        reject("localappdata_unavailable")
    return (
        Path(local_app_data)
        / "ReqSys"
        / "NoteriMigration"
        / "sqlserver"
        / "noteri-20261007T071503"
    )


def run_restore() -> dict[str, Any]:
    if os.name != "nt" or socket.gethostname().casefold() != TARGET_HOST.casefold():
        reject("exact_target_host_required")
    bundle_dir = exact_bundle_dir()
    entries = verify_bundle(bundle_dir)
    selected_names = select_user_databases([entry["database"] for entry in entries])
    selected = {
        entry["database"]: entry
        for entry in entries
        if entry["database"] in USER_DATABASES
    }
    password = validate_password(os.environ.get("MSSQL_SA_PASSWORD"))
    image = prepare_image()
    prepare_volume()
    prepare_container(bundle_dir, image["id"], password)
    version = wait_for_sql(password)
    restored: list[str] = []
    for database in selected_names:
        restore_database(selected[database], password)
        restored.append(database)
    if restored != selected_names:
        reject("restore_count_mismatch")
    for database in selected_names:
        present = _sqlcmd(
            f"SELECT CASE WHEN DB_ID({sql_string(database)}) IS NULL THEN 'ABSENT' ELSE 'PRESENT' END;",
            password,
            code="final_database_check_failed",
        )
        if present != ["PRESENT"]:
            reject("final_database_inventory_mismatch")
    return {
        "schema": RESULT_SCHEMA,
        "ok": True,
        "host": TARGET_HOST,
        "source_host": SOURCE_HOST,
        "manifest_schema": MANIFEST_SCHEMA,
        "backup_files_verified": len(entries),
        "source_restore_verifyonly": True,
        "destination_restore_verifyonly": len(restored),
        "databases_restored": len(restored),
        "database_names": restored,
        "excluded_system_databases": sorted(SYSTEM_DATABASES),
        "checkdb_physical_only": len(restored),
        "restore_with_checksum": True,
        "container": CONTAINER_NAME,
        "volume": VOLUME_NAME,
        "network_mode": "none",
        "backup_mount_read_only": True,
        "image": IMAGE_NAME,
        "image_digest": image["digest"],
        "image_id": image["id"],
        "sql_server_major_version": version,
        "secret_emitted": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.confirm != CONFIRMATION:
            reject("fixed_confirmation_required")
        result = run_restore()
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except RestoreError as exc:
        print(json.dumps({"ok": False, "code": str(exc)}, separators=(",", ":")))
        return 1
    except Exception:  # noqa: BLE001 - never expose runtime details or secrets
        print(json.dumps({"ok": False, "code": "restore_operation_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
