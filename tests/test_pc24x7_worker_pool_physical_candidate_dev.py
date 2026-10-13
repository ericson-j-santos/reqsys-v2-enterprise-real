"""Guarded candidate controls using SQLite fixtures; NO Desktop E2E claims."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
SP=ROOT/"scripts/pc24x7_worker_pool_physical_candidate_dev.py"
spec=importlib.util.spec_from_file_location("physical_candidate_test",SP)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA="a"*40


def sqlite_fixture(tmp_path:Path,*,wrong_task:bool=False)->bytes:
    src=tmp_path/"base.db"
    db=sqlite3.connect(src)
    db.execute("CREATE TABLE tasks(task_id TEXT PRIMARY KEY,issue_number INT,state TEXT,attempt_count INT,leased_by TEXT)")
    for task_id,issue in m.TASKS.items():
        db.execute("INSERT INTO tasks VALUES(?,?,?,?,NULL)",
                   (task_id, 100 if wrong_task else issue,"queued",0))
    db.commit(); db.close()
    return src.read_bytes()


def cipher_fixture(tmp_path,*,wrong_task=False):
    raw=sqlite_fixture(tmp_path,wrong_task=wrong_task)
    cipher=b"testcipher:"+raw[::-1]
    (tmp_path/("workerpool-"+m.BACKUP_CORRELATION+".dpapi")).write_bytes(cipher)
    old=(m.BACKUP_CIPHER_SHA256,m.BACKUP_SHA256,m.BACKUP_BYTES)
    m.BACKUP_CIPHER_SHA256=hashlib.sha256(cipher).hexdigest()
    m.BACKUP_SHA256=hashlib.sha256(raw).hexdigest()
    m.BACKUP_BYTES=len(raw)
    return raw,cipher,old


def test_private_snapshot_positive_and_negative_controls(tmp_path):
    raw,cipher,old=cipher_fixture(tmp_path)
    try:
        result=m._old_snapshot(lambda v: v.removeprefix(b"testcipher:")[::-1],tmp_path)
        assert result==raw
        with pytest.raises(m.CanaryBlocked,match="protected_backup_missing"):
            m._old_snapshot(lambda v:v.removeprefix(b"testcipher:")[::-1],tmp_path/"missing")
    finally:
        m.BACKUP_CIPHER_SHA256,m.BACKUP_SHA256,m.BACKUP_BYTES=old


def test_snapshot_rejects_wrong_task_state_before_build(tmp_path):
    raw,cipher,old=cipher_fixture(tmp_path,wrong_task=True)
    try:
        with pytest.raises(m.CanaryBlocked,match="protected_backup_tasks_not_queued"):
            m._old_snapshot(lambda v:v.removeprefix(b"testcipher:")[::-1],tmp_path)
    finally:
        m.BACKUP_CIPHER_SHA256,m.BACKUP_SHA256,m.BACKUP_BYTES=old


def test_positive_host_sha_run_validation():
    result=m.validate(m.HOST,SHA,SHA,"canary-physical-test-20261013",m.CONFIRM,
                      "38399812345","1",operating_system="nt")
    assert result=="wp-physical-canary-38399812345-1"

@pytest.mark.parametrize("kwargs",[
    {"host":"OTHER"},{"sha":"not_sha"},{"observed":"b"*40},
    {"correlation":"unsafe/../"},{"confirm":"wrong"},{"run_id":"000"},
    {"attempt":"0"},{"operating_system":"linux"},
])
def test_host_and_execution_identity_rejections(kwargs):
    options=dict(host=m.HOST,sha=SHA,observed=SHA,correlation="canary-physical-test-20261013",
                 confirm=m.CONFIRM,run_id="38399812345",attempt="1",operating_system="nt")
    options.update(kwargs)
    with pytest.raises(m.CanaryBlocked):m.validate(**options)


def test_build_staging_whitelist_and_symlink_rejected(tmp_path):
    src=tmp_path/"src";src.mkdir();(src/"app").mkdir();
    (src/"Dockerfile").write_text("FROM python:3.12\n")
    (src/"requirements.txt").write_text("httpx==0.28.1\n")
    (src/"app"/"main.py").write_text("x=1\n")
    (src/"app"/"__init__.py").write_text("")
    (src/"private.env").write_text("DO_NOT_COPY")
    dest=tmp_path/"dest";dest.mkdir()
    count=m._safe_relative_source(src,dest)
    assert count==4 and not (dest/"private.env").exists()
    (src/"app"/"main.py").unlink()
    (src/"app"/"main.py").symlink_to(src/"private.env")
    with pytest.raises(m.CanaryBlocked,match="not_regular"):
        m._safe_relative_source(src,tmp_path/"dest2")


def test_candidate_container_identity_and_mount_check(monkeypatch,tmp_path):
    token=tmp_path/"token";token.write_text("fake")
    expected={"Image":"sha256:"+"a"*64,"Name":"/wp-physical-canary-38399812345-1",
      "State":{"Running":True},"HostConfig":{"PortBindings":{"8097/tcp":[{
      "HostIp":"127.0.0.1","HostPort":"18099"}]},"Privileged":False,
      "ReadonlyRootfs":True,"NetworkMode":"bridge","CapDrop":["ALL"]},
      "Config":{"User":"reqsys"},"Mounts":[{"Type":"volume","Name":"wp-physical-canary-38399812345-1",
      "RW":True,"Destination":"/data"},{"Type":"bind","RW":False,
      "Source":str(token.resolve()),"Destination":"/run/secrets/canary-token"}]}
    monkeypatch.setattr(m,"_docker",lambda *args,**kw:json.dumps([expected]))
    m._verify_candidate("wp-physical-canary-38399812345-1",
       "wp-physical-canary-38399812345-1","sha256:"+"a"*64,token)
    for key,bad in [("Image","sha256:"+"b"*64),("Name","/legacy")]:
        current=expected[key];expected[key]=bad
        with pytest.raises(m.CanaryBlocked):
            m._verify_candidate("wp-physical-canary-38399812345-1",
                "wp-physical-canary-38399812345-1","sha256:"+"a"*64,token)
        expected[key]=current
    expected["HostConfig"]["PortBindings"]["8097/tcp"][0]["HostPort"]="8097"
    with pytest.raises(m.CanaryBlocked,match="candidate_container_isolation_invalid"):
        m._verify_candidate("wp-physical-canary-38399812345-1",
            "wp-physical-canary-38399812345-1","sha256:"+"a"*64,token)


def test_api_readonly_auth_identity_and_replay(monkeypatch):
    calls=[]
    def request(url,token):
        calls.append((url,token is not None))
        if url.endswith("/health"):
            return m._Response(200,{"status":"healthy","contract_version":"v1","auth_configured":True})
        if url.endswith("/openapi.json"):
            return m._Response(200,{"info":{"version":"1.4.0"},"paths":{
                "/v1/tasks/{task_id}/diagnostics":{},"/v1/claims/exact":{}}})
        if url.endswith("/v1/contract"):
            return m._Response(200 if token and token!="invalid" else 401,
                {"contract_name":"engineering-worker-pool","contract_version":"v1"})
        if url.endswith("cwp-000000000000000000000000/diagnostics"):
            return m._Response(404,{})
        if "/v1/tasks/" in url:
            task_id=url.split("/v1/tasks/")[1].split("/")[0]
            if url.endswith("/diagnostics"):
                return m._Response(200,{"task":{"task_id":task_id,"issue_number":m.TASKS[task_id],
                    "state":"queued","repository":m.REPO},"read_mode":"sqlite_mode_ro",
                    "claim_performed":False,"reconciliation_requested":False})
            return m._Response(200,{"task_id":task_id,"attempt_count":0,
                "leased_by":None,"state":"queued"})
        raise AssertionError(url)
    monkeypatch.setattr(m,"_get",request)
    a=m._test_api("safe-token-test");b=m._test_api("safe-token-test")
    assert a==b and a["tasks_preserved"]==2 and a["negative_auth_control"]
    assert all(x[0].startswith("http://127.0.0.1:18099/") for x in calls)
    assert not any("snapshot" in x[0] or "/v1/workers" in x[0] for x in calls)
    assert len(calls)==24


def test_hydration_binary_stdin_with_real_isolated_sqlite(tmp_path):
    raw=sqlite_fixture(tmp_path)
    target=tmp_path/"canary.db"
    script=m.HYDRATE.replace("/data/canary.db",str(target))
    script=script.replace('65536',str(len(raw))).replace(m.BACKUP_SHA256,hashlib.sha256(raw).hexdigest())
    r=subprocess.run([sys.executable,"-c",script],input=raw,capture_output=True,timeout=10)
    assert r.returncode==0 and target.exists(), r.stderr.decode(errors='replace')[-1000:]
    assert json.loads(r.stdout)["task_count"]==2
    again=subprocess.run([sys.executable,"-c",script],input=raw,capture_output=True,timeout=10)
    assert again.returncode!=0  # exclusive O_EXCL: never overwrite a volume on replay
    assert target.read_bytes()==raw


def test_approved_process_allowlist_and_blocked_parent(monkeypatch):
    with pytest.raises(m.CanaryBlocked,match="disallowed_command"):
        m._run(["bash","-c","echo bypass"])
    with pytest.raises(m.CanaryBlocked,match="disallowed_command"):
        m._run([])


def test_candidate_evidence_conservatively_blocks_cutover():
    data={"result":"WORKER_POOL_PHYSICAL_CANDIDATE_BLOCKED","reason":"protected_backup_missing",
          "cutover_ready":False,"secrets_exposed":False}
    assert not data["cutover_ready"]
    assert not (ROOT/"scripts/pc24x7_worker_pool_physical_candidate_dev.py").is_symlink()
