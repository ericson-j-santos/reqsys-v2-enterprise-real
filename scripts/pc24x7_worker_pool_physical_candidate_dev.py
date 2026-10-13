#!/usr/bin/env python3
"""One-shot, fail-closed 1.4 DEV canary on an isolated Docker volume.

Executed ONLY through Session Launcher + Command Gateway in ReqSys DEV.
Does not change the live coordinator, enqueue, register or claim any task.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
HOST = "DESKTOP-PDQK954"
REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
CANDIDATE_REPO = "ericson-j-santos/engineering-worker-pool"
CANDIDATE_SHA = "9074b170d47a7d63a4e0ef6cee2d37282bbbace8"
RULES_SHA = "f6ccb143a581e28650e9b640226f9ef671d469f2"
BACKUP_CORRELATION = "pc24x7-worker-pool-backup-restore-dev-38389083856-1"
BACKUP_SHA256 = "42137c70eaf323f78743ddc734aeaccac066da7df66f093c04631b9bd2ff4452"
BACKUP_CIPHER_SHA256 = "a982d209c7e949f849a42c9fe0fcb1f47638c3cd97219d8622f438cefa8d5b31"
BACKUP_BYTES = 65536
CONFIRM = "CANARY-WORKER-POOL-14-ISOLATED-DEV"
PORT = 18099
EVIDENCE = ROOT / "artifacts" / "pc24x7-worker-pool-physical-canary-dev" / "evidence.json"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
CID = re.compile(r"[a-z0-9][a-z0-9-]{9,135}\Z")
DOCKER_NAME = re.compile(r"wp-physical-canary-[0-9]{4,24}-[1-9][0-9]{0,3}\Z")
TASKS = {"cwp-cdb85c31e3cc4e972f3094ab": 2546,
         "cwp-7d84018f3319356181ab9b47": 2547}

class CanaryBlocked(RuntimeError):
    """Only enumerated codes, no process outputs or private paths."""

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        raise CanaryBlocked("http_redirect_blocked")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise CanaryBlocked(reason)


def _safe_relative_source(source: Path, dest: Path) -> int:
    """Stage ONLY the Dockerfile, pinned requirements and Python app sources."""
    allowed = [source / "Dockerfile", source / "requirements.txt"]
    app = source / "app"
    require(app.is_dir() and not app.is_symlink(), "candidate_app_missing")
    allowed.extend(sorted(app.rglob("*.py")))
    require(4 <= len(allowed) <= 45, "candidate_source_count_invalid")
    total = 0
    for file in allowed:
        require(file.is_file() and not file.is_symlink() and file.stat().st_nlink == 1,
                "candidate_source_not_regular")
        rel = file.relative_to(source)
        require(rel.parts[0] in {"Dockerfile", "requirements.txt", "app"},
                "candidate_source_unexpected")
        require(all(not parent.is_symlink() for parent in file.parents if source in parent.parents),
                "candidate_source_parent_redirected")
        payload = file.read_bytes()
        require(len(payload) < 250_000, "candidate_source_file_oversized")
        total += len(payload)
        require(total < 1_500_000, "candidate_build_context_oversized")
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return len(allowed)


def _run(argv: list[str], *, input_data: bytes | None = None, timeout: int = 55) -> bytes:
    require(bool(argv) and argv[0] in {"docker", "git", "whoami", "icacls"},
            "disallowed_command")
    try:
        proc = subprocess.run(argv, input=input_data, capture_output=True, timeout=timeout,
                              check=False)
    except (OSError, subprocess.SubprocessError):
        raise CanaryBlocked("approved_process_unavailable") from None
    # Docker can print volume, token mount or process details on errors: never expose them.
    require(proc.returncode == 0, "approved_process_failed")
    require(len(proc.stdout) < 160_000, "approved_output_oversized")
    return proc.stdout


def _docker(*args: str, input_data: bytes | None = None, timeout: int = 55) -> str:
    return _run(["docker", *args], input_data=input_data, timeout=timeout).decode("utf-8", errors="replace").strip()


def _checkout(candidate_dir: Path) -> None:
    require(candidate_dir.is_dir() and not candidate_dir.is_symlink(),
            "candidate_source_unavailable")
    head = _run(["git", "-C", str(candidate_dir), "rev-parse", "HEAD"]).decode().strip().lower()
    require(head == CANDIDATE_SHA, "candidate_source_sha_mismatch")
    origin = _run(["git", "-C", str(candidate_dir), "remote", "get-url", "origin"]).decode().strip()
    require(origin.rstrip("/").removesuffix(".git") == "https://github.com/" + CANDIDATE_REPO,
            "candidate_source_remote_mismatch")
    changed = _run(["git", "-C", str(candidate_dir), "status", "--porcelain"]).strip()
    require(not changed, "candidate_source_dirty")


def validate(host: str, sha: str, observed: str, correlation: str,
             confirm: str, run_id: str, attempt: str, *, operating_system: str = os.name) -> str:
    require(host.upper() == HOST and operating_system == "nt" and confirm == CONFIRM,
            "host_or_confirmation_invalid")
    require(bool(SHA40.fullmatch(sha)) and observed == sha, "reqsys_sha_mismatch")
    require(bool(CID.fullmatch(correlation)), "correlation_invalid")
    require(bool(re.fullmatch(r"[0-9]{4,24}", run_id)) and
            bool(re.fullmatch(r"[1-9][0-9]{0,3}", attempt)), "run_identity_invalid")
    name = f"wp-physical-canary-{run_id}-{attempt}"
    require(bool(DOCKER_NAME.fullmatch(name)), "candidate_name_invalid")
    return name


def _private_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", ""))
    require(os.name == "nt" and base.is_absolute() and base.is_dir()
            and not base.is_symlink(), "private_windows_root_invalid")
    root = base / "ReqSys" / "WorkerPoolBackups"
    require(root.is_dir() and not root.is_symlink(), "protected_backup_root_missing")
    return root


def _old_snapshot(decrypt: Callable[[bytes], bytes], root: Path) -> bytes:
    file = root / ("workerpool-" + BACKUP_CORRELATION + ".dpapi")
    require(file.is_file() and not file.is_symlink() and file.stat().st_nlink == 1,
            "protected_backup_missing")
    cipher = file.read_bytes()
    require(hashlib.sha256(cipher).hexdigest() == BACKUP_CIPHER_SHA256,
            "protected_backup_cipher_mismatch")
    try:
        raw = decrypt(cipher)
    except Exception:
        raise CanaryBlocked("protected_backup_dpapi_unavailable") from None
    require(len(raw) == BACKUP_BYTES and hashlib.sha256(raw).hexdigest() == BACKUP_SHA256,
            "protected_backup_identity_mismatch")
    require(raw[:16] == b"SQLite format 3\x00", "protected_backup_header_invalid")
    # Inspect in memory only: never print task records or write a plaintext host DB.
    with sqlite3.connect(":memory:") as db:
        try:
            db.deserialize(raw)
            db.execute("PRAGMA query_only=ON")
            require(db.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                    "protected_backup_integrity_invalid")
            rows = db.execute("SELECT task_id,issue_number,state,attempt_count,leased_by "
                              "FROM tasks WHERE issue_number IN (2546,2547)").fetchall()
            require(len(rows) == 2 and all(TASKS.get(t)==issue and state=="queued"
                    and count==0 and lease is None for t,issue,state,count,lease in rows),
                    "protected_backup_tasks_not_queued")
        except sqlite3.Error:
            raise CanaryBlocked("protected_backup_sqlite_invalid") from None
    return raw


def _restrict_windows_dir(root: Path) -> None:
    """Apply an explicit current-user + SYSTEM DACL; never loosen a parent ACL."""
    sid_csv = _run(["whoami", "/user", "/fo", "csv", "/nh"]).decode("utf-8", "replace")
    try:
        rows = list(csv.reader(sid_csv.splitlines()))
        sid = rows[0][-1]
    except (IndexError, csv.Error):
        raise CanaryBlocked("acl_user_sid_missing") from None
    require(bool(re.fullmatch(r"S-1-5-[0-9-]{5,100}", sid)), "acl_user_sid_invalid")
    _run(["icacls", str(root), "/inheritance:r", "/grant:r",
          "*" + sid + ":(OI)(CI)(F)", "*S-1-5-18:(OI)(CI)(F)"], timeout=20)


# Only this fixed versioned code is passed to the disposable, networkless
# container; unencrypted bytes are piped to stdin, never stored on the host.
HYDRATE = r'''
import hashlib, json, os, sqlite3, sys
raw=sys.stdin.buffer.read(67108865)
if len(raw)!=65536 or raw[:16]!=b"SQLite format 3\x00" or hashlib.sha256(raw).hexdigest()!="42137c70eaf323f78743ddc734aeaccac066da7df66f093c04631b9bd2ff4452":
 raise SystemExit(3)
fd=os.open("/data/canary.db",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"wb") as f:
 f.write(raw); f.flush(); os.fsync(f.fileno())
db=sqlite3.connect("file:/data/canary.db?mode=ro",uri=True)
try:
 db.execute("PRAGMA query_only=ON")
 if db.execute("PRAGMA integrity_check").fetchone()!=('ok',): raise SystemExit(4)
 rows=db.execute("SELECT issue_number,state,attempt_count FROM tasks WHERE issue_number IN (2546,2547)").fetchall()
 if len(rows)!=2 or any(s!='queued' or a!=0 for n,s,a in rows): raise SystemExit(5)
finally: db.close()
print(json.dumps({'hydrated':True,'task_count':len(rows)}))
'''


# Independent SQLite readback is restricted to the candidate container and
# prints aggregate, non-sensitive facts. Unlike /v1/snapshot, this never
# reconciles leases or reads the live coordinator DB.
SQL_READBACK = r'''
import json, sqlite3
con=sqlite3.connect("file:/data/canary.db?mode=ro",uri=True)
try:
 con.execute("PRAGMA query_only=ON")
 rows=con.execute("SELECT issue_number,state,attempt_count,leased_by FROM tasks WHERE issue_number IN (2546,2547) ORDER BY issue_number").fetchall()
 workers=con.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
 if len(rows)!=2 or any((issue not in (2546,2547) or state!="queued" or count!=0 or lease is not None) for issue,state,count,lease in rows):
  raise SystemExit(5)
 print(json.dumps({"tasks_preserved":len(rows),"worker_count":workers,"sqlite_mode_ro":True}))
finally:
 con.close()
'''


def _independent_sqlite(name: str) -> dict[str,Any]:
    receipt=_safe_json(_docker("exec","--user","reqsys",name,
                     "python","-c",SQL_READBACK),"candidate_sql_readback_invalid")
    require(receipt.get("tasks_preserved")==2 and receipt.get("worker_count")==0
            and receipt.get("sqlite_mode_ro") is True,
            "candidate_sql_readback_mismatch")
    return receipt


class _Response:
    def __init__(self, status: int, obj: dict[str, Any]):
        self.status, self.obj = status, obj


def _get(url: str, token: str | None) -> _Response:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers, method="GET")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=6) as response:
            status = response.status
            raw = response.read(131073)
    except HTTPError as exc:
        status, raw = exc.code, b""
    except CanaryBlocked:
        raise
    except (OSError, URLError, TimeoutError):
        raise CanaryBlocked("canary_http_unavailable") from None
    require(status < 300 or status >= 400, "canary_redirect_blocked")
    require(len(raw) <= 131072, "canary_response_oversized")
    try:
        payload = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, UnicodeError):
        raise CanaryBlocked("canary_http_invalid_json") from None
    require(isinstance(payload, dict), "canary_http_invalid_shape")
    return _Response(status, payload)


def _safe_json(raw: str, reason: str) -> Any:
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        raise CanaryBlocked(reason) from None


def _verify_candidate(name: str, volume: str, image_id: str, token_file: Path) -> None:
    obj = _safe_json(_docker("inspect", name), "candidate_docker_inspect_invalid")
    require(isinstance(obj, list) and len(obj)==1, "candidate_container_not_unique")
    c = obj[0]
    host = c.get("HostConfig") or {}
    mounts = c.get("Mounts") or []
    config = c.get("Config") or {}
    binding = ((host.get("PortBindings") or {}).get("8097/tcp") or [])
    require(c.get("Image") == image_id and c.get("Name") == "/"+name and
            (c.get("State") or {}).get("Running") is True and
            host.get("Privileged") is False and host.get("ReadonlyRootfs") is True and
            host.get("NetworkMode") == "bridge" and "ALL" in (host.get("CapDrop") or []) and
            config.get("User") == "reqsys" and len(binding)==1 and
            binding[0].get("HostIp")=="127.0.0.1" and binding[0].get("HostPort")==str(PORT),
            "candidate_container_isolation_invalid")
    require(len(mounts)==2, "candidate_mount_count_invalid")
    mapped={str(x.get("Destination")):x for x in mounts}
    db, token = mapped.get("/data") or {}, mapped.get("/run/secrets/canary-token") or {}
    require(db.get("Type")=="volume" and db.get("Name")==volume and db.get("RW") is True,
            "candidate_volume_identity_invalid")
    require(token.get("Type")=="bind" and token.get("RW") is False and
            Path(str(token.get("Source"))).resolve() == token_file.resolve(),
            "candidate_token_mount_invalid")


def _test_api(token: str) -> dict[str, Any]:
    base = f"http://127.0.0.1:{PORT}"
    for i in range(30):
        try:
            h = _get(base + "/health", None)
            if h.status == 200 and h.obj.get("status") == "healthy":
                break
        except CanaryBlocked:
            pass
        time.sleep(1)
    else:
        raise CanaryBlocked("candidate_health_timeout")
    require(h.obj.get("contract_version")=="v1" and h.obj.get("auth_configured") is True,
            "candidate_health_contract_invalid")
    schema = _get(base + "/openapi.json", None)
    require(schema.status==200 and (schema.obj.get("info") or {}).get("version")=="1.4.0"
            and "/v1/tasks/{task_id}/diagnostics" in (schema.obj.get("paths") or {})
            and "/v1/claims/exact" in (schema.obj.get("paths") or {}),
            "candidate_api_version_invalid")
    require(_get(base+"/v1/contract",None).status==401, "candidate_anonymous_access_invalid")
    require(_get(base+"/v1/contract","invalid").status==401,"candidate_invalid_token_accepted")
    contract = _get(base+"/v1/contract",token)
    require(contract.status==200 and contract.obj.get("contract_name")=="engineering-worker-pool"
            and contract.obj.get("contract_version")=="v1", "candidate_v1_contract_invalid")
    checked=[]
    for task_id,issue in TASKS.items():
        t = _get(base+"/v1/tasks/"+task_id,token)
        d = _get(base+"/v1/tasks/"+task_id+"/diagnostics",token)
        again = _get(base+"/v1/tasks/"+task_id,token)
        task = d.obj.get("task") or {}
        require(t.status==d.status==again.status==200 and
                task.get("task_id")==task_id and task.get("issue_number")==issue and
                task.get("repository")==REPO and task.get("state")=="queued" and
                t.obj.get("task_id")==again.obj.get("task_id")==task_id and
                t.obj.get("attempt_count")==again.obj.get("attempt_count")==0 and
                t.obj.get("leased_by") is None and again.obj.get("leased_by") is None and
                d.obj.get("read_mode")=="sqlite_mode_ro" and d.obj.get("claim_performed") is False and
                d.obj.get("reconciliation_requested") is False,
                "candidate_task_identity_or_state_invalid")
        checked.append(issue)
    require(_get(base+"/v1/tasks/cwp-000000000000000000000000/diagnostics",token).status==404,
            "candidate_unknown_task_negative_failed")
    return {"tasks_preserved":len(checked),"checked_issues":checked,"negative_auth_control":True}


def run_canary(*, sha: str, correlation: str, confirm: str, run_id: str,
               attempt: str, candidate_dir: Path, decrypt: Callable[[bytes],bytes],
               checkout_sha: Callable[[],str]) -> dict[str,Any]:
    name=validate(socket.gethostname(),sha,checkout_sha(),correlation,confirm,run_id,attempt)
    require(Path(os.environ.get("GITHUB_WORKSPACE",""),"_worker_pool_candidate").resolve()==candidate_dir.resolve(),
            "candidate_checkout_path_mismatch")
    _checkout(candidate_dir)
    # The live coordinator is inspected, never stopped, restarted or used as a mount.
    helper_path=Path(__file__).resolve().with_name("pc24x7_worker_pool_inventory_dev.py")
    require(helper_path.is_file() and not helper_path.is_symlink(),"inventory_helper_missing")
    helper_spec=importlib.util.spec_from_file_location("candidate_inventory",helper_path)
    require(helper_spec is not None and helper_spec.loader is not None,"inventory_helper_invalid")
    module=importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(module)
    try:
        original, original_image=module._container_id(lambda args:_docker(*args))
    except Exception:
        raise CanaryBlocked("legacy_container_readback_failed") from None
    root=_private_root()
    raw=_old_snapshot(decrypt,root)
    volume=name
    image_tag="wp-physical-candidate:"+run_id+"-"+attempt
    token = secrets.token_hex(32)
    volume_created=image_created=container_started=False
    cleanup_ok=False
    candidate={}
    td: Path | None = None
    temp_root=root/"candidate-temp"
    require(not temp_root.is_symlink(),"candidate_private_redirected")
    temp_root.mkdir(exist_ok=True)
    _restrict_windows_dir(temp_root)
    try:
        td=Path(tempfile.mkdtemp(prefix=name+"-",dir=temp_root))
        if td.is_symlink():
            raise CanaryBlocked("private_stage_redirected")
        stage=td/"build"
        stage.mkdir()
        count=_safe_relative_source(candidate_dir,stage)
        token_file=td/"canary-token"
        with token_file.open("xb") as out:
            out.write(token.encode("ascii"));out.flush();os.fsync(out.fileno())
        os.chmod(token_file,0o600)
        # Name reservation is fail-closed. No reusing or deleting unknown volumes.
        require(not _docker("ps","-a","--filter","name=^/"+name+"$","--format","{{.ID}}").strip(),
                "canary_container_collision")
        require(not _docker("volume","ls","--filter","name=^"+volume+"$","--format","{{.Name}}").strip(),
                "canary_volume_collision")
        # Unique per dispatch; never overwrite a previous tag.
        image_list=_docker("images",image_tag,"--format","{{.ID}}")
        require(not image_list.strip(),"candidate_image_tag_collision")
        _docker("build","--pull","--label","org.opencontainers.image.revision="+CANDIDATE_SHA,
                "-t",image_tag,str(stage),timeout=170)
        image_created=True
        images=_safe_json(_docker("image","inspect",image_tag),"candidate_image_inspect_invalid")
        require(isinstance(images,list) and len(images)==1,"candidate_image_not_unique")
        info=images[0]
        image_id=str(info.get("Id") or "")
        require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}",image_id)) and
                (info.get("Config") or {}).get("Labels",{}).get("org.opencontainers.image.revision")==CANDIDATE_SHA,
                "candidate_image_provenance_invalid")
        _docker("volume","create",volume)
        volume_created=True
        # A disposable networkless helper transfers DB bytes only via stdin.
        out=_docker("run","--rm","-i","--network","none","--read-only",
            "--security-opt","no-new-privileges","--cap-drop","ALL",
            "--user","reqsys","--mount",f"type=volume,src={volume},dst=/data",
            image_tag,"python","-c",HYDRATE,input_data=raw,timeout=60)
        proof=_safe_json(out,"canary_hydration_receipt_invalid")
        require(proof.get("hydrated") is True and proof.get("task_count")==2,
                "canary_hydration_invalid")
        container_started=True  # exact name was confirmed absent; clean partial Docker runs too
        _docker("run","-d","--name",name,"--network","bridge",
            "--publish",f"127.0.0.1:{PORT}:8097", "--read-only",
            "--tmpfs","/tmp:rw,noexec,nosuid,size=16m", "--cap-drop","ALL",
            "--security-opt","no-new-privileges","--pids-limit","128",
            "--memory","512m","--user","reqsys",
            "--mount",f"type=volume,src={volume},dst=/data",
            "--mount",f"type=bind,src={token_file},dst=/run/secrets/canary-token,readonly",
            "--env","CODEX_WORKER_POOL_DB=/data/canary.db",
            "--env","CODEX_WORKER_POOL_API_TOKEN_FILE=/run/secrets/canary-token",
            "--env","CODEX_WORKER_POOL_EXPECTED_RULES_SHA="+RULES_SHA,
            "--env","CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS=300",
            image_tag,timeout=30)
        _verify_candidate(name,volume,image_id,token_file)
        candidate=_test_api(token)
        readback=_independent_sqlite(name)
        require(readback["tasks_preserved"]==candidate["tasks_preserved"],
                "candidate_sql_vs_api_mismatch")
        candidate["independent_sqlite_readback"]=True
        # Same existing legacy identity confirms candidate did not replace it.
        original_after, image_after=module._container_id(lambda args:_docker(*args))
        require((original_after,image_after)==(original,original_image),
                "legacy_container_changed")
        candidate.update({"candidate_image_id":image_id,"staged_source_files":count,
                          "legacy_container_unchanged":True})
    finally:
        # All removals target only the exact name, volume and tag created here.
        problems=[]
        for created,commands in (
            (container_started,("rm","-f",name)),
            (volume_created,("volume","rm",volume)),
            (image_created,("image","rm",image_tag)),
        ):
            if created:
                try:_docker(*commands,timeout=30)
                except CanaryBlocked:problems.append(commands[0])
        try:
            require(not _docker("ps","-a","--filter","name=^/"+name+"$","--format","{{.ID}}").strip(),
                    "canary_container_cleanup_failed")
            require(not _docker("volume","ls","--filter","name=^"+volume+"$","--format","{{.Name}}").strip(),
                    "canary_volume_cleanup_failed")
        except CanaryBlocked:
            problems.append("readback")
        if td is not None:
            try:
                shutil.rmtree(td)
            except OSError:
                problems.append("private_temp_cleanup")
        cleanup_ok=not problems
        if not cleanup_ok:
            raise CanaryBlocked("canary_cleanup_or_readback_blocked")
    original_final,image_final=module._container_id(lambda args:_docker(*args))
    require((original_final,image_final)==(original,original_image),
            "legacy_container_final_readback_failed")
    return {
        "result":"WORKER_POOL_PHYSICAL_CANDIDATE_PROVEN", "environment":"dev",
        "host":HOST,"source_sha":sha,"candidate_sha":CANDIDATE_SHA,
        "correlation_id":correlation,"candidate_image_id_sha256":candidate["candidate_image_id"][7:],
        "source_file_count":candidate["staged_source_files"],
        "tasks_preserved":candidate["tasks_preserved"],
        "negative_auth_control":candidate["negative_auth_control"],
        "legacy_container_unchanged":True,"independent_sqlite_readback":True,
        "private_snapshot_reused":True,
        "isolated_volume_used":True,"candidate_cleanup_verified":cleanup_ok,
        "candidate_image_digest_attested_on_desktop":True,
        "isolated_candidate_canary_passed":True,
        "rollback_rehearsal_passed":False,
        "builder_registered":False,"validator_registered":False,
        "claim_performed":False,"enqueue_performed":False,"live_database_modified":False,
        "secrets_exposed":False,"production_touched":False,"cutover_ready":False,
    }


def _read_head() -> str:
    return _run(["git","-C",str(ROOT),"rev-parse","HEAD"]).decode().strip().lower()


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--expected-sha",required=True)
    parser.add_argument("--correlation-id",required=True)
    parser.add_argument("--confirm",required=True)
    args=parser.parse_args()
    try:
        require(os.environ.get("GITHUB_ACTIONS")=="true" and
                os.environ.get("GITHUB_REPOSITORY")==REPO,
                "untrusted_execution_context")
        run_id=os.environ.get("GITHUB_RUN_ID", "")
        attempt=os.environ.get("GITHUB_RUN_ATTEMPT", "")
        candidate_dir=Path(os.environ.get("GITHUB_WORKSPACE",""))/"_worker_pool_candidate"
        helper_path=Path(__file__).resolve().with_name("pc24x7_worker_pool_backup_restore_dev.py")
        require(helper_path.is_file() and not helper_path.is_symlink(),"backup_helper_missing")
        spec=importlib.util.spec_from_file_location("candidate_backup",helper_path)
        require(spec is not None and spec.loader is not None,"backup_helper_invalid")
        helper=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        result=run_canary(sha=args.expected_sha,correlation=args.correlation_id,
                          confirm=args.confirm,run_id=run_id,attempt=attempt,
                          candidate_dir=candidate_dir,decrypt=lambda b:helper.dpapi(b,encrypt=False),
                          checkout_sha=_read_head)
        code=0
    except CanaryBlocked as exc:
        result={"result":"WORKER_POOL_PHYSICAL_CANDIDATE_BLOCKED","reason":str(exc),
                "cutover_ready":False,"production_touched":False,"secrets_exposed":False,
                "live_database_modified":False}
        code=2
    except Exception:
        result={"result":"WORKER_POOL_PHYSICAL_CANDIDATE_BLOCKED",
                "reason":"candidate_unavailable","cutover_ready":False,
                "production_touched":False,"secrets_exposed":False,"live_database_modified":False}
        code=2
    EVIDENCE.parent.mkdir(parents=True,exist_ok=True)
    EVIDENCE.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    return code

if __name__ == "__main__":
    raise SystemExit(main())
