#!/usr/bin/env python3
"""DEV-only physical candidate canary, isolated from the live Worker Pool.

A new candidate is built from one pinned repository checkout into a deliberately
minimal Docker context. It owns a unique Docker container, image tag and volume.
No command changes the live Compose service, its volume, tokens, or task leases.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_FILE = Path(__file__).resolve().with_name("pc24x7_worker_pool_inventory_dev.py")
if not INVENTORY_FILE.is_file() or INVENTORY_FILE.is_symlink():
    raise RuntimeError("pinned_inventory_missing")
_spec = importlib.util.spec_from_file_location("candidate_inventory", INVENTORY_FILE)
if _spec is None or _spec.loader is None:
    raise RuntimeError("pinned_inventory_unloadable")
inventory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inventory)

HOST = "DESKTOP-PDQK954"
RULES_SHA = "f6ccb143a581e28650e9b640226f9ef671d469f2"
WORKER_SHA = "9074b170d47a7d63a4e0ef6cee2d37282bbbace8"
CONFIRM = "CANARY-WORKER-POOL-DEV-ISOLATED"
REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
URL = "http://127.0.0.1:18098"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
CORRELATION = re.compile(r"pc24x7-workerpool-canary-[0-9]{6,18}-[1-9][0-9]?\Z")
EVIDENCE = ROOT / "artifacts" / "pc24x7-worker-pool-candidate-canary-dev" / "evidence.json"

SQL_READBACK = """
import sqlite3, json
db = sqlite3.connect("file:/data/canary.db?mode=ro", uri=True)
try:
    db.execute("PRAGMA query_only=ON")
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = db.execute("PRAGMA foreign_key_check").fetchone()
    tasks = db.execute("SELECT task_id,issue_number,state,leased_by,attempt_count FROM tasks").fetchall()
    workers = db.execute("SELECT count(*) FROM workers").fetchone()[0]
    lanes = db.execute("SELECT repository,enabled FROM repository_lanes").fetchall()
    print(json.dumps({"integrity":integrity,"foreign_key_violation":foreign is not None,
                      "tasks":tasks,"workers":workers,"lanes":lanes}))
finally:
    db.close()
"""


class CanaryBlocked(RuntimeError):
    """Only fixed, sanitized reason codes."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise CanaryBlocked(code)


def execute(argv: list[str], *, timeout: int = 30, can_fail: bool = False) -> tuple[int, str]:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                check=False)
    except (OSError, subprocess.SubprocessError):
        raise CanaryBlocked("restricted_subprocess_unavailable") from None
    require(len(result.stdout) <= 160_000, "output_size_limit")
    if not can_fail:
        require(result.returncode == 0, "restricted_subprocess_failed")
    return result.returncode, result.stdout.strip()


def git(source: Path, *args: str) -> str:
    return execute(["git", "-C", str(source), *args], timeout=15)[1]


def preconditions(*, host: str, expected_sha: str, observed_sha: str,
                  worker_sha: str, correlation_id: str, confirm: str) -> None:
    require(host.upper() == HOST and confirm == CONFIRM and
            SHA40.fullmatch(expected_sha) is not None and expected_sha == observed_sha and
            worker_sha == WORKER_SHA and CORRELATION.fullmatch(correlation_id) is not None,
            "host_sha_confirmation_or_correlation_invalid")


def source_checkout(workspace: Path, expected_sha: str) -> Path:
    require(workspace.is_dir() and not workspace.is_symlink(), "workspace_invalid")
    source = workspace / "_worker_candidate"
    require(source.is_dir() and not source.is_symlink() and
            source.resolve().parent == workspace.resolve(), "candidate_source_untrusted")
    require(git(source, "rev-parse", "HEAD") == expected_sha, "worker_source_sha_invalid")
    origin = git(source, "remote", "get-url", "origin")
    require(origin in {"https://github.com/ericson-j-santos/engineering-worker-pool",
                       "https://github.com/ericson-j-santos/engineering-worker-pool.git"},
            "worker_source_remote_invalid")
    require(not git(source, "status", "--porcelain"), "worker_source_dirty")
    for relative in ("Dockerfile", "requirements.txt", "app/main.py"):
        path = source / relative
        require(path.is_file() and not path.is_symlink(), "worker_source_files_missing")
    return source


def safe_staging(source: Path, target: Path) -> None:
    """Never pass the checkout, .git, runner paths or secrets as Docker build context."""
    require(not target.exists(), "context_collision")
    paths = [source / "Dockerfile", source / "requirements.txt"]
    app = source / "app"
    require(app.is_dir() and not app.is_symlink(), "candidate_app_missing")
    paths.extend(path for path in app.rglob("*") if path.is_file())
    require(len(paths) <= 160 and all(path.is_file() and not path.is_symlink() and
            source.resolve() in path.resolve().parents for path in paths),
            "candidate_context_untrusted")
    require(sum(p.stat().st_size for p in paths) <= 8 * 1024 * 1024,
            "candidate_context_oversized")
    target.mkdir(mode=0o700)
    for path in paths:
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    require(len(list(target.rglob("*"))) >= 3 and
            not (target / ".git").exists() and not (target / ".env").exists(),
            "candidate_context_invalid")


def candidate_identity(payload: dict[str, Any], *, image: str, name: str,
                       volume: str, token_file: Path) -> None:
    """Validate the actual Docker object before sending any test request."""
    conf, host = payload.get("Config") or {}, payload.get("HostConfig") or {}
    ports = (host.get("PortBindings") or {}).get("8097/tcp") or []
    mounts = payload.get("Mounts") or []
    by_target = {m.get("Destination"): m for m in mounts if isinstance(m, dict)}
    data = by_target.get("/data") or {}
    token = by_target.get("/run/secrets/canary-token") or {}
    require(payload.get("Name") == "/" + name and payload.get("Image") == image
            and (payload.get("State") or {}).get("Running") is True
            and host.get("Privileged") is False and host.get("ReadonlyRootfs") is True
            and "ALL" in (host.get("CapDrop") or [])
            and host.get("NetworkMode") == "bridge" and conf.get("User") == "reqsys"
            and len(ports) == 1 and ports[0].get("HostIp") == "127.0.0.1"
            and ports[0].get("HostPort") == "18098",
            "candidate_runtime_or_port_invalid")
    require(len(mounts) == 2 and data.get("Type") == "volume"
            and data.get("Name") == volume and data.get("RW") is True
            and token.get("Type") == "bind" and token.get("RW") is False
            and Path(str(token.get("Source") or "")).resolve() == token_file.resolve(),
            "candidate_mount_isolation_invalid")


def legacy_readback() -> tuple[str, str, dict[str, Any]]:
    try:
        container, image = inventory._container_id(lambda args: execute(["docker", *args])[1])
        raw = execute(["docker", "exec", "--user", "reqsys", container,
                       "python", "-c", inventory.SQL_PROBE], timeout=25)[1]
        payload = inventory._validate_inventory(json.loads(raw))
    except (inventory.InventoryBlocked, ValueError, TypeError, KeyError):
        raise CanaryBlocked("live_service_identity_or_readback_invalid") from None
    return container, image, payload


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, msg, headers, newurl):
        raise CanaryBlocked("candidate_redirect_refused")


def request(method: str, url: str, token: str, body: dict[str, Any] | None):
    require(url.startswith(URL + "/") and url.count("://") == 1, "candidate_url_invalid")
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, data=encoded, method=method, headers=headers),
                         timeout=5) as response:
            raw = response.read(160_001)
            require(len(raw) <= 160_000, "candidate_response_oversized")
            return response.status, json.loads(raw) if raw else {}
    except HTTPError as err:
        return err.code, {}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        raise CanaryBlocked("candidate_http_unavailable") from None


def wait_for_candidate_health(token: str) -> None:
    """Retry only transient startup unavailability, never policy or validation faults."""
    for _attempt in range(26):
        try:
            code, health = request("GET", URL + "/health", token, None)
            if code == 200 and health.get("status") == "healthy":
                return
        except CanaryBlocked as exc:
            if str(exc) != "candidate_http_unavailable":
                raise
        time.sleep(0.5)
    raise CanaryBlocked("candidate_not_ready")


def e2e(token: str, expected_sha: str, correlation_id: str, name: str) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts import pending_development_worker_pool_bridge as bridge

    wait_for_candidate_health(token)
    contract_code, contract = request("GET", URL + "/v1/contract", token, None)
    require(contract_code == 200 and contract.get("contract_name") == "engineering-worker-pool"
            and contract.get("contract_version") == "v1", "candidate_contract_invalid")
    openapi_code, openapi = request("GET", URL + "/openapi.json", token, None)
    require(openapi_code == 200 and openapi.get("info", {}).get("version") == "1.4.0",
            "candidate_version_invalid")
    require(request("GET", URL + "/v1/contract", "invalid", None)[0] == 401,
            "candidate_negative_auth_invalid")
    require(request("GET", URL + "/v1/tasks/invalid/diagnostics", token, None)[0] == 422,
            "candidate_negative_task_invalid")
    lane, configured = request("POST", URL + "/v1/repositories", token, {
        "repository": REPO, "enabled": False, "max_in_flight": 1,
        "correlation_id": correlation_id[:128],
    })
    require(lane == 200 and configured.get("enabled") is False, "candidate_lane_unsafe")
    report = bridge.direct_report(REPO, 2020, "main", correlation_id)
    result = bridge.enqueue_local_work(report, base_sha=expected_sha, pool_url=URL,
                                       token=token, request_fn=request,
                                       allow_legacy_fallback=False, allow_work_fallback=False)
    items = result.get("items") or []
    require(result.get("result") == "WORKER_POOL_ENQUEUED"
            and result.get("contract_mode") == "v1"
            and result.get("dispatch_modes") == ["work_v1"]
            and result.get("legacy_fallback_used") is False
            and len(items) == 1 and items[0].get("created") is True
            and items[0].get("replay_created") is False
            and items[0].get("independent_readback") is True,
            "candidate_reqsys_consumer_e2e_invalid")
    task_id = items[0].get("task_id")
    diag_code, diag = request("GET", URL + f"/v1/tasks/{task_id}/diagnostics", token, None)
    require(diag_code == 200 and diag.get("claim_performed") is False
            and diag.get("task", {}).get("state") == "queued"
            and diag.get("precheck_eligible_workers") == 0,
            "candidate_diagnostics_invalid")
    raw = execute(["docker", "exec", "--user", "reqsys", name,
                   "python", "-c", SQL_READBACK], timeout=25)[1]
    try:
        db = json.loads(raw)
    except ValueError:
        raise CanaryBlocked("candidate_sqlite_readback_invalid") from None
    rows = db.get("tasks") or []
    require(db.get("integrity") == "ok" and db.get("foreign_key_violation") is False
            and len(rows) == 1 and rows[0][0] == task_id
            and rows[0][1] == 2020 and rows[0][2] == "queued"
            and rows[0][3] is None and rows[0][4] == 0
            and db.get("workers") == 0 and db.get("lanes") == [[REPO, 0]],
            "candidate_sqlite_readback_mismatch")
    return {"authenticated_reqsys_consumer_e2e": True, "negative_auth_control": True,
            "replay_idempotent": True, "independent_sqlite_readback": True,
            "contract_version": "v1", "application_version": "1.4.0",
            "synthetic_task_count": 1, "worker_count": 0}


def canary(*, host: str, expected_sha: str, observed_sha: str, worker_sha: str,
           correlation_id: str, confirm: str, workspace: Path, private_root: Path):
    preconditions(host=host, expected_sha=expected_sha, observed_sha=observed_sha,
                  worker_sha=worker_sha, correlation_id=correlation_id, confirm=confirm)
    source = source_checkout(workspace, worker_sha)
    require(private_root.is_dir() and not private_root.is_symlink(),
            "private_root_unavailable")
    legacy_before = legacy_readback()
    name = "wp-canary-" + correlation_id.removeprefix("pc24x7-workerpool-canary-")
    volume, tag = name, "wp-candidate:" + name.removeprefix("wp-canary-")
    built = created_volume = created_container = False
    image_id = ""
    cleanup_ok = False
    temporary = None
    try:
        temporary = Path(tempfile.mkdtemp(prefix="workerpool-candidate-", dir=private_root))
        stage = temporary
        safe_staging(source, stage / "context")
        token_path = stage / "test-token"
        with token_path.open("x", encoding="utf-8") as output:
            output.write(secrets.token_urlsafe(48))
        token = token_path.read_text(encoding="utf-8").strip()
        # Reject resource collisions; never adopt or delete another run's resources.
        require(execute(["docker", "container", "inspect", name], can_fail=True)[0] != 0
                and execute(["docker", "volume", "inspect", volume], can_fail=True)[0] != 0
                and execute(["docker", "image", "inspect", tag], can_fail=True)[0] != 0,
                "candidate_resource_already_exists")
        execute(["docker", "build", "--quiet", "--pull",
                 "--label", f"org.opencontainers.image.revision={worker_sha}",
                 "-t", tag, str(stage / "context")], timeout=140)
        built = True
        image = json.loads(execute(["docker", "image", "inspect", tag])[1])
        require(len(image) == 1 and image[0].get("Id", "").startswith("sha256:")
                and (image[0].get("Config") or {}).get("Labels", {}).get(
                    "org.opencontainers.image.revision") == worker_sha,
                "candidate_image_sha_invalid")
        image_id = image[0]["Id"]
        execute(["docker", "volume", "create", "--label",
                 "com.reqsys.workerpool.canary=" + correlation_id, volume])
        created_volume = True
        cid = execute(["docker", "run", "--detach", "--name", name,
                       "--network", "bridge", "--publish", "127.0.0.1:18098:8097",
                       "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                       "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                       "--pids-limit", "128", "--memory", "512m",
                       "--label", "com.reqsys.workerpool.canary=" + correlation_id,
                       "--mount", f"type=volume,src={volume},dst=/data",
                       "--mount", f"type=bind,src={token_path},dst=/run/secrets/canary-token,readonly",
                       "--env", "CODEX_WORKER_POOL_DB=/data/canary.db",
                       "--env", "CODEX_WORKER_POOL_API_TOKEN_FILE=/run/secrets/canary-token",
                       "--env", "CODEX_WORKER_POOL_EXPECTED_RULES_SHA=" + RULES_SHA,
                       "--env", "CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS=300",
                       tag], timeout=35)[1]
        require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None,
                "candidate_id_invalid")
        created_container = True
        candidate = json.loads(execute(["docker", "inspect", cid])[1])
        require(len(candidate) == 1, "candidate_inspect_invalid")
        candidate_identity(candidate[0], image=image_id, name=name, volume=volume,
                           token_file=token_path)
        require((candidate[0].get("Config") or {}).get("Labels", {}).get(
            "com.reqsys.workerpool.canary") == correlation_id,
            "candidate_label_identity_invalid")
        outcome = e2e(token, expected_sha, correlation_id, cid)
        legacy_after = legacy_readback()
        require(legacy_before == legacy_after, "live_legacy_readback_changed")
    finally:
        # Never execute docker compose/down, prune, or remove any resource not
        # exclusively created by this correlation. Failure is a blocking result.
        failures = []
        if not created_container:
            try:
                status, raw = execute(["docker", "inspect", name], can_fail=True)
                if status == 0:
                    objects = json.loads(raw)
                    owned = (len(objects) == 1 and
                             (objects[0].get("Config") or {}).get("Labels", {}).get(
                                 "com.reqsys.workerpool.canary") == correlation_id)
                    if owned:
                        execute(["docker", "rm", "-f", name], timeout=20)
                    else:
                        failures.append("unowned_container_collision")
            except (CanaryBlocked, ValueError, TypeError):
                failures.append("unverified_container_cleanup")
        for enabled, args in (
            (created_container, ["docker", "rm", "-f", name]),
            (created_volume, ["docker", "volume", "rm", volume]),
            (built, ["docker", "image", "rm", tag]),
        ):
            if enabled:
                try:
                    execute(args, timeout=20)
                except CanaryBlocked:
                    failures.append("cleanup_failed")
        if temporary is not None:
            try:
                shutil.rmtree(temporary)
            except OSError:
                failures.append("private_canary_cleanup_failed")
        cleanup_ok = not failures
        if not cleanup_ok:
            raise CanaryBlocked("canary_cleanup_incomplete")
    require(cleanup_ok, "canary_cleanup_incomplete")
    return {
        "result": "WORKER_POOL_DEV_PHYSICAL_ISOLATED_CANARY_VERIFIED",
        "environment": "dev", "host": HOST, "source_sha": expected_sha,
        "worker_pool_sha": worker_sha, "rules_sha": RULES_SHA,
        "correlation_id": correlation_id,
        "candidate_image_id": image_id, "isolated_port": 18098,
        "isolated_volume_cleaned": True, "candidate_container_cleaned": True,
        "synthetic_only": True, "physical_candidate_canary_passed": True,
        "real_backup_imported_into_candidate": False,
        "rollback_rehearsal_passed": False, "cutover_ready": False,
        "legacy_container_unchanged": True, "live_database_modified": False,
        "claim_performed": False, "production_touched": False,
        "secrets_exposed": False, **outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--worker-pool-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        require(os.name == "nt", "physical_windows_host_required")
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        require(local.is_absolute() and local.is_dir() and not local.is_symlink(),
                "private_profile_unavailable")
        private = local / "ReqSys" / "WorkerPoolCanary"
        private.mkdir(parents=True, exist_ok=True)
        checkout = execute(["git", "-C", str(ROOT), "rev-parse", "HEAD"])[1]
        result = canary(host=socket.gethostname(), expected_sha=args.expected_sha,
                        observed_sha=checkout, worker_sha=args.worker_pool_sha,
                        correlation_id=args.correlation_id, confirm=args.confirm,
                        workspace=Path(os.environ.get("GITHUB_WORKSPACE", "")),
                        private_root=private)
        code = 0
    except CanaryBlocked as exc:
        result = {"result": "WORKER_POOL_DEV_PHYSICAL_CANARY_BLOCKED",
                  "reason": str(exc), "cutover_ready": False,
                  "physical_candidate_canary_passed": False,
                  "production_touched": False, "secrets_exposed": False}
        code = 2
    except Exception:
        result = {"result": "WORKER_POOL_DEV_PHYSICAL_CANARY_BLOCKED",
                  "reason": "candidate_execution_unavailable", "cutover_ready": False,
                  "physical_candidate_canary_passed": False,
                  "production_touched": False, "secrets_exposed": False}
        code = 2
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
