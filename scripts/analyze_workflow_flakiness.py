#!/usr/bin/env python3
"""Build a read-only inventory of GitHub Actions workflow flakiness."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

def load_object(path: Path) -> dict[str, Any]:
    payload=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload,dict): raise ValueError(f'{path} must contain a JSON object')
    return payload

def classify(sample_size:int, rerun_rate:float, failure_rate:float, cancellation_rate:float)->str:
    if sample_size<5: return 'insufficient_sample'
    if failure_rate>=0.20 or rerun_rate>=0.25: return 'high'
    if failure_rate>=0.10 or rerun_rate>=0.10 or cancellation_rate>=0.20: return 'medium'
    return 'low'

def analyze_flakiness(*,runs_payload:dict[str,Any],observed_at:datetime|None=None)->dict[str,Any]:
    runs=runs_payload.get('workflow_runs') or []
    if not isinstance(runs,list): raise ValueError('workflow_runs must be a list')
    grouped:dict[str,list[dict[str,Any]]]=defaultdict(list); ignored=0
    for run in runs:
        if not isinstance(run,dict) or not str(run.get('name') or '').strip(): ignored+=1; continue
        grouped[str(run['name']).strip()].append(run)
    workflows=[]
    for name,items in grouped.items():
        total=len(items); successes=sum(i.get('conclusion')=='success' for i in items); failures=sum(i.get('conclusion') in {'failure','timed_out','action_required','startup_failure'} for i in items); cancelled=sum(i.get('conclusion')=='cancelled' for i in items); reruns=sum(int(i.get('run_attempt') or 1)>1 for i in items); incomplete=sum(i.get('status')!='completed' for i in items); first=sum(int(i.get('run_attempt') or 1)==1 and i.get('conclusion')=='success' for i in items)
        rr=reruns/total if total else 0.0; fr=failures/total if total else 0.0; cr=cancelled/total if total else 0.0
        workflows.append({'workflow':name,'sample_size':total,'successes':successes,'failures':failures,'cancelled':cancelled,'reruns':reruns,'incomplete':incomplete,'first_cycle_successes':first,'first_cycle_success_rate':round(first/total,4) if total else 0.0,'rerun_rate':round(rr,4),'terminal_failure_rate':round(fr,4),'cancellation_rate':round(cr,4),'risk':classify(total,rr,fr,cr)})
    order={'high':0,'medium':1,'low':2,'insufficient_sample':3}; workflows.sort(key=lambda i:(order[i['risk']],-i['terminal_failure_rate'],-i['rerun_rate'],i['workflow']))
    timestamp=observed_at or datetime.now(UTC)
    return {'schema_version':'1.0.0','contract':'reqsys-workflow-flakiness-inventory','observed_at':timestamp.astimezone(UTC).isoformat(),'runs_analyzed':len(runs),'workflows_analyzed':len(workflows),'ignored_records':ignored,'high_risk_workflows':[i['workflow'] for i in workflows if i['risk']=='high'],'medium_risk_workflows':[i['workflow'] for i in workflows if i['risk']=='medium'],'workflows':workflows,'automatic_workflow_disable_allowed':False,'automatic_required_check_change_allowed':False,'production_touched':False}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--runs',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); report=analyze_flakiness(runs_payload=load_object(a.runs)); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(report,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
