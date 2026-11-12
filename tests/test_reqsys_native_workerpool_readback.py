"""Tests for existing Worker Pool GET readback. Fixtures are NOT physical proof."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from scripts.reqsys_native_workerpool_readback import (
    WorkerPoolGET, read_workerpool_checkpoint,
)
from scripts.validate_reqsys_native_dev_profile import NativeAdmissionBlocked

SHA="a"*40
DIGEST="b"*64
TASK="cwp-"+"c"*24
WORKER="desktop-pdqk954"
NOW=datetime(2026,11,12,1,0,tzinfo=timezone.utc)
EXP=(NOW+timedelta(minutes=4)).isoformat()
BASE="/v1/tasks/"+TASK
REPO="ericson-j-santos/reqsys-v2-enterprise-real"

def records():
    task={"task_id":TASK,"repository":REPO,"base_sha":SHA,
          "state":"running","leased_by":WORKER,"lease_expires_at":EXP,
          "lease_generation":2,"attempt_id":"attempt-a","fencing_required":True}
    diagnosis={"read_mode":"postgres_read_only","task":dict(task,lease_expired_observed=False),
               "claim_performed":False,"reconciliation_requested":False}
    cp={"checkpoint":{"task_id":TASK,"lease_generation":2,"artifact_sha256":DIGEST,
                      "effect_state":"confirmed","checkpoint_id":"checkpoint-a"}}
    return task,diagnosis,cp

def observed(t=None,d=None,c=None,after=None,**changes):
    t0,d0,c0=records()
    t=t if t is not None else t0
    d=d if d is not None else d0
    c=c if c is not None else c0
    second=after if after is not None else deepcopy(t)
    paths=[]
    def get(path):
        paths.append(path)
        return deepcopy({BASE:t,BASE+"/diagnostics":d,BASE+"/checkpoints/latest":c}[path]) if len(paths)<4 else deepcopy(second)
    args={"get":get,"task_id":TASK,"expected_source_sha":SHA,
          "expected_worker_id":WORKER,"expected_generation":2,
          "expected_artifact_sha256":DIGEST,"at":NOW}
    args.update(changes)
    return read_workerpool_checkpoint(**args),paths

def test_positive_and_replay():
    one,paths=observed()
    assert one==observed()[0]
    assert paths==[BASE,BASE+"/diagnostics",BASE+"/checkpoints/latest",BASE]
    assert one["status"]=="WORKER_POOL_READBACK_ONLY"
    assert one["ready_for_work"] is False
    assert one["lease_exclusive_certified"] is False
    assert one["physical_host_authenticated"] is False
    assert one["continuity_certified"] is False

@pytest.mark.parametrize("field,invalid",[
    ("repository","other/repo"),("base_sha","f"*40),("leased_by","other-worker"),
    ("lease_generation",1),("state","completed"),("fencing_required",False),
    ("lease_expires_at","2020-01-01T00:00:00+00:00"),
])
def test_task_tamper(field,invalid):
    t,d,c=records()
    t[field]=invalid
    with pytest.raises(NativeAdmissionBlocked):
        observed(t=t)

def test_read_only_diagnostics_required():
    t,d,c=records()
    d["read_mode"]="sqlite_mode_ro"
    with pytest.raises(NativeAdmissionBlocked):
        observed(d=d)

def test_diagnostics_race_rejected():
    t,d,c=records()
    d["task"]["lease_expires_at"]="2030-01-01T00:00:00+00:00"
    with pytest.raises(NativeAdmissionBlocked):
        observed(d=d)

def test_lease_changed_during_readback():
    t,d,c=records()
    after=deepcopy(t)
    after["lease_generation"]=3
    with pytest.raises(NativeAdmissionBlocked,match="workerpool_concurrent_change"):
        observed(after=after)

@pytest.mark.parametrize("mutation",[
    {"artifact_sha256":"f"*64},{"lease_generation":1},
    {"task_id":"cwp-"+"d"*24},{"effect_state":"pending"},{"effect_state":"unknown"},
])
def test_checkpoint_tamper(mutation):
    t,d,c=records()
    c["checkpoint"].update(mutation)
    with pytest.raises(NativeAdmissionBlocked):
        observed(c=c)

def test_no_network_auth_without_token(tmp_path):
    with pytest.raises(NativeAdmissionBlocked,match="workerpool_token_unavailable"):
        WorkerPoolGET(origin="https://api.example.org",token_file=tmp_path/"missing")

def test_private_token_permissions(tmp_path):
    token=tmp_path/"token"
    token.write_text("Q"*32)
    token.chmod(0o644)
    with pytest.raises(NativeAdmissionBlocked,match="workerpool_token_permissions"):
        WorkerPoolGET(origin="https://api.example.org",token_file=token)

def test_no_unapproved_routes(tmp_path):
    token=tmp_path/"token"
    token.write_text("Q"*32)
    token.chmod(0o600)
    client=WorkerPoolGET(origin="https://api.example.org",token_file=token)
    with pytest.raises(NativeAdmissionBlocked,match="workerpool_route_forbidden"):
        client.get("/v1/tasks")
    with pytest.raises(NativeAdmissionBlocked,match="workerpool_route_forbidden"):
        client.get(BASE+"/start")
