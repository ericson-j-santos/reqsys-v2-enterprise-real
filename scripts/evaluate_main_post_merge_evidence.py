#!/usr/bin/env python3
"""Evaluate whether post-merge workflows produced evidence for the current main SHA."""
from __future__ import annotations
import argparse, json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
ALLOWED_EVENTS = {"push", "workflow_run", "workflow_dispatch", "schedule"}
ALLOWED_CONCLUSIONS = {"success", "neutral", "skipped"}

def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict): raise ValueError(f"{path} must contain a JSON object")
    return payload

def latest_runs_by_name(runs: list[dict[str, Any]], main_sha: str) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict) or str(run.get("head_sha") or "") != main_sha: continue
        branch = str(run.get("head_branch") or "")
        if branch and branch != "main": continue
        if str(run.get("event") or "") not in ALLOWED_EVENTS: continue
        name = str(run.get("name") or "").strip()
        if not name: continue
        current = selected.get(name)
        key = (int(run.get("run_attempt") or 0), str(run.get("created_at") or ""), int(run.get("id") or 0))
        current_key = (int(current.get("run_attempt") or 0), str(current.get("created_at") or ""), int(current.get("id") or 0)) if current else (-1, "", -1)
        if current is None or key > current_key: selected[name] = run
    return selected

def evaluate_post_merge(*, runs_payload: dict[str, Any], main_sha: str, required_workflows: list[str], observed_at: datetime | None = None) -> dict[str, Any]:
    required = [item.strip() for item in required_workflows if item.strip()]
    if not main_sha: raise ValueError("main_sha must not be empty")
    if not required: raise ValueError("required_workflows must not be empty")
    runs = runs_payload.get("workflow_runs") or []
    if not isinstance(runs, list): raise ValueError("workflow_runs must be a list")
    latest = latest_runs_by_name(runs, main_sha)
    missing, incomplete, failed, observed = [], [], [], []
    for workflow in required:
        run = latest.get(workflow)
        if run is None:
            missing.append(workflow); observed.append({"workflow": workflow, "status": "missing", "conclusion": "missing"}); continue
        status, conclusion = str(run.get("status") or ""), str(run.get("conclusion") or "")
        observed.append({"workflow": workflow, "run_id": int(run.get("id") or 0), "status": status, "conclusion": conclusion, "event": str(run.get("event") or ""), "url": str(run.get("html_url") or "")})
        if status != "completed": incomplete.append({"workflow": workflow, "status": status})
        elif conclusion not in ALLOWED_CONCLUSIONS: failed.append({"workflow": workflow, "conclusion": conclusion})
    ready = not missing and not incomplete and not failed
    decision = "post_merge_evidence_missing" if missing else "post_merge_workflow_incomplete" if incomplete else "post_merge_workflow_failed" if failed else "post_merge_evidence_ready"
    timestamp = observed_at or datetime.now(UTC)
    return {"schema_version":"1.0.0","contract":"reqsys-main-post-merge-evidence","observed_at":timestamp.astimezone(UTC).isoformat(),"main_sha":main_sha,"required_workflows":required,"observed_workflows":observed,"missing_workflows":missing,"incomplete_workflows":incomplete,"failed_workflows":failed,"ready":ready,"decision":decision,"absence_is_success":False,"automatic_issue_closure_allowed":False,"production_touched":False}

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--runs",type=Path,required=True); p.add_argument("--main-sha",required=True); p.add_argument("--required-workflow",action="append",required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--strict",action="store_true"); a=p.parse_args()
    report=evaluate_post_merge(runs_payload=load_object(a.runs),main_sha=a.main_sha,required_workflows=a.required_workflow)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False)); return 1 if a.strict and not report["ready"] else 0
if __name__ == "__main__": raise SystemExit(main())
