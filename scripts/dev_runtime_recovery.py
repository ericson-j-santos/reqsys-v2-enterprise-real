#!/usr/bin/env python3
"""Closed-scope capture, preservation and rollback for PC24x7 DEV."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path, PurePath
from typing import Protocol

HOST = "DESKTOP-PDQK954"
ENV = "dev"
PROJECT = "wt-pc24x7-piloto"
SERVICES = ("api", "frontend", "nginx")
ROOT = Path(r"C:\dev\chatgpt-workers\wt-pc24x7-public-dev-governed")
IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
PREPARE_CONFIRM = "PREPARE-ROLLBACK-PC24X7-PUBLIC-DEV"
ROLLBACK_CONFIRM = "ROLLBACK-PC24X7-PUBLIC-DEV"
LEGACY_DB_PROBE = """import json
from app.db import SessionLocal
from sqlalchemy import text
s=None
try:
 s=SessionLocal(); value=s.execute(text("SELECT 1")).scalar(); ok=value==1
 print(json.dumps({"database_ok":ok,"category":"ok" if ok else "unexpected_result"},sort_keys=True,separators=(",",":")))
 raise SystemExit(0 if ok else 1)
except SystemExit: raise
except Exception:
 print('{"category":"query_failed","database_ok":false}'); raise SystemExit(1)
finally:
 if s is not None:
  try:s.close()
  except Exception:pass
"""


class RecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Runner(Protocol):
    def run(
        self, argv: Sequence[str], timeout: int = 30, input_text: str | None = None
    ) -> Result: ...


class SubprocessRunner:
    def run(self, argv, timeout=30, input_text=None):
        p = subprocess.run(
            list(argv),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return Result(p.returncode, p.stdout, p.stderr)


def invoke(runner, argv, timeout=30, input_text=None, allow_failure=False):
    r = runner.run(tuple(argv), timeout, input_text)
    if r.returncode and not allow_failure:
        raise RecoveryError(
            f"command_failed:{argv[0]}:{argv[1] if len(argv) > 1 else 'unknown'}"
        )
    return r


def checked(runner, argv, timeout=30, input_text=None):
    return invoke(runner, argv, timeout, input_text).stdout


def parsed_output(result):
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RecoveryError("invalid_metadata") from exc


def parsed(runner, argv):
    return parsed_output(invoke(runner, argv))


def observed_scope(hostname=None):
    if (hostname or socket.gethostname()).upper() != HOST:
        raise RecoveryError("host_identity_refused")


def _reparse(path):
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def safe_relative(path, root):
    root_abs = Path(os.path.abspath(root))
    path_abs = Path(os.path.abspath(path))
    if _reparse(root_abs):
        raise RecoveryError("root_reparse_refused")
    try:
        rel = path_abs.relative_to(root_abs)
    except ValueError as exc:
        raise RecoveryError("external_path_refused") from exc
    if ".." in PurePath(path).parts:
        raise RecoveryError("traversal_refused")
    cursor = root_abs
    for part in rel.parts:
        cursor = cursor / part
        if _reparse(cursor):
            raise RecoveryError("link_refused")
    resolved_root = root_abs.resolve(strict=True)
    resolved = path_abs.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RecoveryError("external_path_refused") from exc
    if not resolved.is_file():
        raise RecoveryError("non_file_refused")
    return rel


def file_meta(path, root):
    rel = safe_relative(path, root)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return {
        "relative_path": rel.as_posix(),
        "size": path.stat().st_size,
        "sha256": h.hexdigest(),
    }


def image_id(value):
    value = str(value).lower()
    if not IMAGE.fullmatch(value):
        raise RecoveryError("invalid_image_id")
    return value


def unique_container(runner, service):
    out = checked(
        runner,
        (
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "--format",
            "{{.ID}}",
        ),
    )
    ids = [x.strip() for x in out.splitlines() if x.strip()]
    if len(ids) != 1:
        raise RecoveryError(f"container_cardinality:{service}")
    return ids[0]


def inspect_container(runner, cid, service, root):
    data = parsed(runner, ("docker", "inspect", cid))
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise RecoveryError("invalid_container_metadata")
    item = data[0]
    labels = (item.get("Config") or {}).get("Labels") or {}
    if (
        labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.service") != service
    ):
        raise RecoveryError("compose_identity_mismatch")
    if Path(labels.get("com.docker.compose.project.working_dir", "")).resolve(
        strict=True
    ) != root.resolve(strict=True):
        raise RecoveryError("working_dir_mismatch")
    return item, labels


def _load_identity_probe():
    """Load only the attested sibling when running the standalone CLI."""
    if __package__ == "scripts":
        from scripts import probe_pc24x7_dev_runtime_identity as probe
    else:
        source = Path(__file__).with_name("probe_pc24x7_dev_runtime_identity.py")
        if source.is_symlink() or not source.is_file():
            raise RecoveryError("live_probe_source_unavailable")
        spec = spec_from_file_location("_reqsys_fixed_pc24x7_probe", source)
        if spec is None or spec.loader is None:
            raise RecoveryError("live_probe_loader_unavailable")
        probe = module_from_spec(spec)
        spec.loader.exec_module(probe)
    probe_error = getattr(probe, "ProbeError", None)
    run = getattr(probe, "run", None)
    if (
        not isinstance(probe_error, type)
        or not issubclass(probe_error, Exception)
        or not callable(run)
    ):
        raise RecoveryError("live_probe_contract_invalid")
    return probe_error, run


def observe_identity():
    ProbeError, run = _load_identity_probe()
    try:
        result = run("0" * 40)
    except ProbeError as exc:
        raise RecoveryError("live_probe_unavailable") from exc
    build = str(
        result["routes"]["/api/runtime/build-info"].get("build_sha", "")
    ).lower()
    if result.get("identity_validated") is not True or not SHA.fullmatch(build):
        raise RecoveryError("live_identity_invalid")
    for route in ("/api/runtime/health", "/api/runtime/readiness"):
        item = result["routes"].get(route, {})
        if item.get("status_invalid_type") is True or str(
            item.get("status", "")
        ).casefold() not in {"healthy", "ready", "ok"}:
            raise RecoveryError("live_readiness_invalid")
    liveness = result["routes"].get("/api/runtime/liveness", {})
    if liveness.get("alive_invalid_type") is True:
        raise RecoveryError("live_liveness_invalid")
    if liveness.get("status_invalid_type") is True:
        raise RecoveryError("live_liveness_invalid")
    if "alive" in liveness and (
        type(liveness["alive"]) is not bool or liveness["alive"] is not True
    ):
        raise RecoveryError("live_liveness_invalid")
    if "status" in liveness and (
        not isinstance(liveness["status"], str)
        or liveness["status"].casefold() not in {"alive", "healthy", "ok"}
    ):
        raise RecoveryError("live_liveness_invalid")
    if liveness.get("alive") is not True and str(
        liveness.get("status", "")
    ).casefold() not in {"alive", "healthy", "ok"}:
        raise RecoveryError("live_liveness_invalid")
    return build


def static_live_guard(runner, root=ROOT, hostname=None):
    observed_scope(hostname)
    root_abs = Path(os.path.abspath(root))
    if _reparse(root_abs) or root_abs.resolve(strict=True) != root_abs:
        raise RecoveryError("runtime_root_invalid")
    containers = {}
    for service in SERVICES:
        cid = unique_container(runner, service)
        item, _ = inspect_container(runner, cid, service, root)
        containers[service] = {
            "container_id": cid,
            "image_id": image_id(item.get("Image")),
        }
    return {
        "host": HOST,
        "root": str(root_abs),
        "containers": containers,
    }


def live_guard(runner, root=ROOT, identity_probe=observe_identity, hostname=None):
    live = static_live_guard(runner, root, hostname)
    live["runtime_sha"] = identity_probe()
    return live


def fingerprint(body):
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def seal(body):
    value = dict(body)
    value["fingerprint"] = fingerprint(value)
    return value


def ordered_label(value):
    result = []
    for raw in str(value or "").split(","):
        item = raw.strip()
        if item and item not in result:
            result.append(item)
    return result


def capture(runner, root=ROOT, identity_probe=observe_identity, hostname=None):
    live = live_guard(runner, root, identity_probe, hostname)
    configs_by_service = {}
    envfiles_by_service = {}
    for service in SERVICES:
        _, labels = inspect_container(
            runner, live["containers"][service]["container_id"], service, root
        )
        current_configs = ordered_label(
            labels.get("com.docker.compose.project.config_files", "")
        )
        current_env = ordered_label(
            labels.get("com.docker.compose.project.environment_file", "")
        )
        if not current_configs:
            raise RecoveryError("compose_config_missing")
        configs_by_service[service] = [
            file_meta(Path(item), root) for item in current_configs
        ]
        envfiles_by_service[service] = [
            file_meta(Path(item), root) for item in current_env
        ]
    body = {
        "schema": 3,
        "state": "captured",
        "host": live["host"],
        "environment": ENV,
        "project": PROJECT,
        "runtime_root": live["root"],
        "runtime_sha": live["runtime_sha"],
        "services": live["containers"],
        "compose_files_by_service": configs_by_service,
        "environment_files_by_service": envfiles_by_service,
    }
    # Keep the schema-2 projection only when one ordered source really applies
    # to every service.  Older private manifests remain readable, while a
    # partially recreated stack can no longer be flattened into an unsafe
    # synthetic Compose order.
    if len({json.dumps(value, sort_keys=True) for value in configs_by_service.values()}) == 1:
        body["compose_files"] = configs_by_service[SERVICES[0]]
    if len({json.dumps(value, sort_keys=True) for value in envfiles_by_service.values()}) == 1:
        body["environment_files"] = envfiles_by_service[SERVICES[0]]
    return seal(body)


def service_file_records(manifest, by_service_key, legacy_key):
    grouped = manifest.get(by_service_key)
    if grouped is None:
        legacy = manifest.get(legacy_key)
        if not isinstance(legacy, list):
            raise RecoveryError("file_metadata_invalid")
        return {service: legacy for service in SERVICES}
    if not isinstance(grouped, dict) or set(grouped) != set(SERVICES):
        raise RecoveryError("file_metadata_invalid")
    if any(not isinstance(grouped.get(service), list) for service in SERVICES):
        raise RecoveryError("file_metadata_invalid")
    return grouped


def validate(manifest, runner, expected_fingerprint, root=ROOT, require_prepared=False):
    if not expected_fingerprint or manifest.get("fingerprint") != expected_fingerprint:
        raise RecoveryError("external_fingerprint_mismatch")
    unsigned = {k: v for k, v in manifest.items() if k != "fingerprint"}
    if fingerprint(unsigned) != expected_fingerprint:
        raise RecoveryError("manifest_integrity_failed")
    if (
        manifest.get("host") != HOST
        or manifest.get("environment") != ENV
        or manifest.get("project") != PROJECT
    ):
        raise RecoveryError("scope_refused")
    if Path(str(manifest.get("runtime_root"))).resolve(strict=True) != root.resolve(
        strict=True
    ):
        raise RecoveryError("runtime_root_mismatch")
    if not SHA.fullmatch(str(manifest.get("runtime_sha", ""))):
        raise RecoveryError("runtime_sha_invalid")
    services = manifest.get("services")
    if not isinstance(services, dict) or set(services) != set(SERVICES):
        raise RecoveryError("service_set_mismatch")
    for service in SERVICES:
        if not isinstance(services[service], dict):
            raise RecoveryError("service_metadata_invalid")
        expected = image_id(services[service].get("image_id"))
        checked(runner, ("docker", "image", "inspect", expected))
        if require_prepared:
            verify_tag(runner, str(services[service].get("rollback_tag", "")), expected)
    groups = [
        service_file_records(
            manifest, "environment_files_by_service", "environment_files"
        )
    ]
    if require_prepared:
        originals = service_file_records(
            manifest, "compose_files_by_service", "compose_files"
        )
        rollback_files = service_file_records(
            manifest,
            "rollback_compose_files_by_service",
            "rollback_compose_files",
        )
        if any(
            not rollback_files[service]
            or len(rollback_files[service]) != len(originals[service])
            for service in SERVICES
        ):
            raise RecoveryError("rollback_compose_files_invalid")
        groups.append(rollback_files)
    else:
        groups.append(
            service_file_records(manifest, "compose_files_by_service", "compose_files")
        )
    for grouped in groups:
        for records in grouped.values():
            for record in records:
                if (
                    not isinstance(record, dict)
                    or file_meta(root / str(record.get("relative_path")), root)
                    != record
                ):
                    raise RecoveryError("runtime_file_changed")
    if require_prepared:
        if manifest.get("state") != "prepared":
            raise RecoveryError("manifest_not_prepared")
        if (
            file_meta(root / manifest["rollback_override"]["relative_path"], root)
            != manifest["rollback_override"]
        ):
            raise RecoveryError("override_changed")


def rollback_tag(service, sha):
    return f"reqsys-rollback/{PROJECT}-{service}:{sha}"


def verify_tag(runner, tag, expected):
    result = invoke(runner, ("docker", "image", "inspect", tag), allow_failure=True)
    if result.returncode:
        raise RecoveryError("rollback_tag_missing")
    data = parsed_output(result)
    if (
        not isinstance(data, list)
        or len(data) != 1
        or image_id(data[0].get("Id")) != expected
    ):
        raise RecoveryError("rollback_tag_collision")


def prepare(manifest, runner, expected_fingerprint, root=ROOT):
    validate(manifest, runner, expected_fingerprint, root)
    sha = manifest["runtime_sha"]
    services = {k: dict(v) for k, v in manifest["services"].items()}
    for service in SERVICES:
        expected = services[service]["image_id"]
        tag = rollback_tag(service, sha)
        existing = invoke(
            runner, ("docker", "image", "inspect", tag), allow_failure=True
        )
        if existing.returncode == 0:
            data = parsed_output(existing)
            if (
                not isinstance(data, list)
                or len(data) != 1
                or image_id(data[0].get("Id")) != expected
            ):
                raise RecoveryError("rollback_tag_collision")
        else:
            checked(runner, ("docker", "image", "tag", expected, tag))
        verify_tag(runner, tag, expected)
        services[service]["rollback_tag"] = tag
    override = {
        "services": {s: {"image": services[s]["rollback_tag"]} for s in SERVICES}
    }
    recovery_dir = root / ".reqsys-recovery"
    if recovery_dir.exists() and (_reparse(recovery_dir) or not recovery_dir.is_dir()):
        raise RecoveryError("recovery_dir_refused")
    recovery_dir.mkdir(exist_ok=True)
    compose_files_by_service = service_file_records(
        manifest, "compose_files_by_service", "compose_files"
    )
    rollback_compose_files_by_service = {}
    snapshot_cache = {}
    for service in SERVICES:
        rollback_compose_files_by_service[service] = []
        for index, record in enumerate(compose_files_by_service[service]):
            cache_key = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if cache_key in snapshot_cache:
                rollback_compose_files_by_service[service].append(
                    snapshot_cache[cache_key]
                )
                continue
            source = root / record["relative_path"]
            snapshot = recovery_dir / (
                f"compose-{service}-{index:02d}-{expected_fingerprint}.yaml"
            )
            try:
                payload = source.read_bytes()
                if snapshot.exists():
                    if _reparse(snapshot) or snapshot.read_bytes() != payload:
                        raise RecoveryError("compose_snapshot_collision")
                else:
                    flags = (
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_BINARY", 0)
                    )
                    descriptor = os.open(snapshot, flags, 0o600)
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(payload)
                        stream.flush()
                        os.fsync(stream.fileno())
            except RecoveryError:
                raise
            except OSError as exc:
                raise RecoveryError("compose_snapshot_write_failed") from exc
            snapshot_record = file_meta(snapshot, root)
            snapshot_cache[cache_key] = snapshot_record
            rollback_compose_files_by_service[service].append(snapshot_record)
    path = recovery_dir / f"rollback-{expected_fingerprint}.json"
    payload = json.dumps(override, sort_keys=True, separators=(",", ":"))
    if path.exists():
        if _reparse(path) or path.read_text(encoding="utf-8") != payload:
            raise RecoveryError("override_collision")
    else:
        path.write_text(payload, encoding="utf-8")
    body = {k: v for k, v in manifest.items() if k != "fingerprint"}
    body.update(
        {
            "state": "prepared",
            "services": services,
            "rollback_compose_files_by_service": rollback_compose_files_by_service,
            "rollback_override": file_meta(path, root),
            "capture_fingerprint": expected_fingerprint,
        }
    )
    if len({
        json.dumps(value, sort_keys=True)
        for value in rollback_compose_files_by_service.values()
    }) == 1:
        body["rollback_compose_files"] = rollback_compose_files_by_service[
            SERVICES[0]
        ]
    return seal(body)


def legacy_database_probe(runner, api):
    try:
        result = invoke(
            runner,
            ("docker", "exec", "-i", api, "python", "-B", "-"),
            30,
            LEGACY_DB_PROBE,
            allow_failure=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise RecoveryError("database_probe_timeout") from exc
    try:
        data = json.loads(result.stdout)
    except ValueError as exc:
        raise RecoveryError("database_probe_invalid") from exc
    if result.returncode or data != {"database_ok": True, "category": "ok"}:
        raise RecoveryError("database_probe_failed")


def deploy_check(
    expected_sha,
    runner,
    root=ROOT,
    identity_probe=observe_identity,
    hostname=None,
    wait_timeout=90,
    wait_interval=2,
    clock=time.monotonic,
    sleeper=time.sleep,
):
    if not SHA.fullmatch(str(expected_sha).lower()):
        raise RecoveryError("expected_sha_invalid")
    try:
        live = wait_live(
            runner,
            str(expected_sha).lower(),
            root,
            identity_probe,
            hostname,
            wait_timeout,
            wait_interval,
            clock,
            sleeper,
            diagnose_timeout=True,
        )
    except RecoveryError as exc:
        if str(exc) == "readiness_timeout":
            raise RecoveryError("deploy_readiness_timeout") from exc
        raise
    api = unique_container(runner, "api")
    legacy_database_probe(runner, api)
    return {
        "deploy_check_ok": True,
        "environment": ENV,
        "project": PROJECT,
        "runtime_sha": live["runtime_sha"],
        "database_ok": True,
    }


def restored(runner, manifest, root):
    for service in SERVICES:
        cid = unique_container(runner, service)
        item, _ = inspect_container(runner, cid, service, root)
        if image_id(item.get("Image")) != manifest["services"][service]["image_id"]:
            raise RecoveryError("restored_image_mismatch")


def rollback_compose_base(manifest, service, root):
    environment_files = service_file_records(
        manifest, "environment_files_by_service", "environment_files"
    )[service]
    compose_files = service_file_records(
        manifest,
        "rollback_compose_files_by_service",
        "rollback_compose_files",
    )[service]
    base = [
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--project-directory",
        str(root),
    ]
    for record in environment_files:
        base.extend(("--env-file", str(root / record["relative_path"])))
    for record in compose_files:
        base.extend(("--file", str(root / record["relative_path"])))
    base.extend(
        ("--file", str(root / manifest["rollback_override"]["relative_path"]))
    )
    return base


def same_rollback_source(manifest, left, right):
    environments = service_file_records(
        manifest, "environment_files_by_service", "environment_files"
    )
    compose_files = service_file_records(
        manifest,
        "rollback_compose_files_by_service",
        "rollback_compose_files",
    )
    return (
        environments[left] == environments[right]
        and compose_files[left] == compose_files[right]
    )


_DEV_READINESS_REASON_MAP = {
    "command_failed": "container_unavailable",
    "container_cardinality": "container_unavailable",
    "invalid_container_metadata": "container_unavailable",
    "invalid_image_id": "container_unavailable",
    "invalid_metadata": "container_unavailable",
    "host_identity_refused": "scope_invalid",
    "runtime_root_invalid": "scope_invalid",
    "compose_identity_mismatch": "scope_invalid",
    "working_dir_mismatch": "scope_invalid",
    "live_probe_source_unavailable": "probe_invalid",
    "live_probe_loader_unavailable": "probe_invalid",
    "live_probe_contract_invalid": "probe_invalid",
    "live_probe_unavailable": "probe_unavailable",
    "live_identity_invalid": "unhealthy",
    "live_readiness_invalid": "unhealthy",
    "live_liveness_invalid": "unhealthy",
}


def _dev_readiness_reason(error: RecoveryError) -> str:
    """Return only a fixed category, never exception details or host paths."""
    return _DEV_READINESS_REASON_MAP.get(str(error).split(":", 1)[0], "unknown")


def wait_live(
    runner,
    expected_sha,
    root,
    identity_probe,
    hostname,
    timeout,
    interval,
    clock,
    sleeper,
    diagnose_timeout=False,
):
    deadline = clock() + timeout
    last_reason = "unknown"
    observed_sha_mismatch = False
    while True:
        try:
            live = live_guard(runner, root, identity_probe, hostname)
            if live["runtime_sha"] == expected_sha:
                return live
            if diagnose_timeout:
                observed_sha_mismatch = True
        except RecoveryError as exc:
            if diagnose_timeout:
                last_reason = _dev_readiness_reason(exc)
                if last_reason in {"scope_invalid", "probe_invalid"}:
                    raise RecoveryError(f"deploy_readiness_{last_reason}") from None
        if clock() >= deadline:
            if diagnose_timeout:
                category = "sha_mismatch" if observed_sha_mismatch else last_reason
                raise RecoveryError(f"deploy_readiness_{category}")
            raise RecoveryError("readiness_timeout")
        sleeper(interval)


def rollback(
    manifest,
    runner,
    expected_fingerprint,
    root=ROOT,
    identity_probe=observe_identity,
    hostname=None,
    wait_timeout=90,
    wait_interval=2,
    clock=time.monotonic,
    sleeper=time.sleep,
    allow_unhealthy_current=False,
):
    try:
        validate(manifest, runner, expected_fingerprint, root, True)
        old = manifest["runtime_sha"]
        try:
            live_guard(runner, root, identity_probe, hostname)
        except RecoveryError as exc:
            if not allow_unhealthy_current or str(exc).split(":", 1)[0] not in {
                "live_probe_unavailable",
                "live_identity_invalid",
                "live_readiness_invalid",
                "live_liveness_invalid",
            }:
                raise
            # A candidate API indisponível não pode impedir o rollback. Ainda
            # exigimos host, raiz, projeto, cardinalidade e imagens observadas.
            static_live_guard(runner, root, hostname)
        if same_rollback_source(manifest, "api", "frontend"):
            application_phases = (("api", "frontend"),)
        else:
            # Restore frontend first so the API remains available until its own
            # exact source chain is ready to be replayed.
            application_phases = (("frontend",), ("api",))
        for phase in application_phases:
            base = rollback_compose_base(manifest, phase[0], root)
            checked(
                runner,
                (
                    *base,
                    "up",
                    "-d",
                    "--no-build",
                    "--no-deps",
                    "--force-recreate",
                    *phase,
                ),
                300,
            )
        wait_live(
            runner,
            old,
            root,
            identity_probe,
            hostname,
            wait_timeout,
            wait_interval,
            clock,
            sleeper,
        )
        legacy_database_probe(runner, unique_container(runner, "api"))
        validate(manifest, runner, expected_fingerprint, root, True)
        live_guard(runner, root, identity_probe, hostname)
        base = rollback_compose_base(manifest, "nginx", root)
        checked(
            runner,
            (*base, "up", "-d", "--no-build", "--no-deps", "--force-recreate", "nginx"),
            120,
        )
        wait_live(
            runner,
            old,
            root,
            identity_probe,
            hostname,
            wait_timeout,
            wait_interval,
            clock,
            sleeper,
        )
        restored(runner, manifest, root)
        return {"rollback_ok": True, "project": PROJECT, "runtime_sha": old}
    except Exception as exc:
        if isinstance(exc, RecoveryError):
            raise RecoveryError(f"rollback_failed:{exc}") from exc
        raise RecoveryError("rollback_failed:unexpected") from exc


def load(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecoveryError("manifest_invalid")
    return value


def save(path, value):
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )


def _deploy_check_cli_error_category(exc: Exception) -> str:
    """Return an allowlisted diagnostic code, never a raw exception message."""
    if isinstance(exc, subprocess.TimeoutExpired):
        return "runtime_subprocess_timeout"
    if isinstance(exc, PermissionError):
        return "runtime_permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "runtime_file_missing"
    if isinstance(exc, ImportError):
        return "runtime_dependency_missing"
    if isinstance(exc, OSError):
        return "runtime_os_error"
    return "runtime_payload_invalid"

def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "mode", choices=("capture", "prepare", "validate", "rollback", "deploy-check")
    )
    p.add_argument("--manifest", type=Path)
    p.add_argument("--expected-fingerprint")
    p.add_argument("--expected-sha")
    p.add_argument("--confirm")
    a = p.parse_args()
    runner = SubprocessRunner()
    try:
        if a.mode == "deploy-check":
            try:
                out = deploy_check(a.expected_sha, runner)
            except (
                OSError, ImportError, KeyError, TypeError, ValueError,
                AttributeError, IndexError, subprocess.TimeoutExpired,
            ) as exc:
                raise RecoveryError(_deploy_check_cli_error_category(exc)) from None
        elif a.manifest is None:
            raise RecoveryError("manifest_required")
        elif a.mode == "capture":
            value = capture(runner)
            save(a.manifest, value)
            out = {"capture_ok": True, "fingerprint": value["fingerprint"]}
        elif a.mode == "prepare":
            if a.confirm != PREPARE_CONFIRM:
                raise RecoveryError("confirmation_refused")
            value = prepare(load(a.manifest), runner, a.expected_fingerprint)
            save(a.manifest, value)
            out = {
                "prepare_ok": True,
                "fingerprint": value["fingerprint"],
                "capture_fingerprint": value["capture_fingerprint"],
            }
        elif a.mode == "validate":
            validate(
                load(a.manifest), runner, a.expected_fingerprint, require_prepared=True
            )
            out = {"manifest_valid": True}
        else:
            if a.confirm != ROLLBACK_CONFIRM:
                raise RecoveryError("confirmation_refused")
            out = rollback(load(a.manifest), runner, a.expected_fingerprint)
        print(json.dumps(out, sort_keys=True, separators=(",", ":")))
        return 0
    except RecoveryError as exc:
        print(
            json.dumps(
                {"ok": False, "category": str(exc).split(":", 1)[0]},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
