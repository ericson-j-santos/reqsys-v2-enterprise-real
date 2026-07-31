from datetime import UTC, datetime
import pytest
from scripts.evaluate_main_post_merge_evidence import evaluate_post_merge
NOW=datetime(2026,7,31,20,0,tzinfo=UTC)
def run(name,sha="abc",status="completed",conclusion="success",event="push",run_id=1,branch="main"):
    return {"id":run_id,"name":name,"head_sha":sha,"head_branch":branch,"event":event,"status":status,"conclusion":conclusion,"created_at":f"2026-07-31T20:00:{run_id:02d}Z","run_attempt":1,"html_url":f"https://example.test/runs/{run_id}"}
def evaluate(runs,required=None): return evaluate_post_merge(runs_payload={"workflow_runs":runs},main_sha="abc",required_workflows=required or ["Padrão Ouro Delivery Automation"],observed_at=NOW)
def test_ready(): assert evaluate([run("Padrão Ouro Delivery Automation")])["ready"] is True
def test_missing_is_not_success():
    r=evaluate([]); assert r["decision"]=="post_merge_evidence_missing" and r["absence_is_success"] is False
def test_incomplete_and_failed():
    r=evaluate([run("Padrão Ouro Delivery Automation",status="in_progress",conclusion=None),run("Branch Protection Audit",conclusion="failure",run_id=2)],["Padrão Ouro Delivery Automation","Branch Protection Audit"]); assert r["incomplete_workflows"] and r["failed_workflows"]
def test_other_event_or_sha_rejected(): assert evaluate([run("Padrão Ouro Delivery Automation",event="pull_request"),run("Padrão Ouro Delivery Automation",sha="old",run_id=2)])["ready"] is False
def test_latest_attempt_wins():
    a=run("Padrão Ouro Delivery Automation",conclusion="failure",run_id=1); b=run("Padrão Ouro Delivery Automation",run_id=2); b["run_attempt"]=2; assert evaluate([a,b])["ready"] is True
def test_invalid():
    with pytest.raises(ValueError): evaluate_post_merge(runs_payload={"workflow_runs":[]},main_sha="",required_workflows=["x"])
    with pytest.raises(ValueError): evaluate_post_merge(runs_payload={"workflow_runs":"x"},main_sha="abc",required_workflows=["x"])
