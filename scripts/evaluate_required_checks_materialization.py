#!/usr/bin/env python3
"""Evaluate whether configured required checks materialize on sampled PR head SHAs."""
from __future__ import annotations
import argparse, json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

def load_object(path: Path)->dict[str,Any]:
    payload=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload,dict): raise ValueError(f'{path} must contain a JSON object')
    return payload

def required_contexts(protection:dict[str,Any])->list[str]:
    if protection.get('unavailable'): return []
    contexts=set()
    raw=protection.get('contexts') or []
    if isinstance(raw,list): contexts.update(str(i).strip() for i in raw if str(i).strip())
    checks=protection.get('checks') or []
    if isinstance(checks,list):
        for item in checks:
            if isinstance(item,dict) and str(item.get('context') or '').strip(): contexts.add(str(item['context']).strip())
    return sorted(contexts)

def evaluate_materialization(*,protection_payload:dict[str,Any],samples_payload:dict[str,Any],observed_at:datetime|None=None)->dict[str,Any]:
    required=required_contexts(protection_payload); samples=samples_payload.get('samples') or []
    if not isinstance(samples,list): raise ValueError('samples must be a list')
    if protection_payload.get('unavailable'): decision='branch_protection_unavailable'; inconclusive=True
    elif not required: decision='no_required_checks_configured'; inconclusive=True
    elif not samples: decision='no_pr_samples_available'; inconclusive=True
    else: decision='required_checks_materialized'; inconclusive=False
    normalized=[]; missing_by={c:[] for c in required}
    for sample in samples:
        if not isinstance(sample,dict): continue
        sha=str(sample.get('sha') or '').strip(); pr=int(sample.get('pr_number') or 0); raw=sample.get('contexts') or []; contexts=sorted({str(i).strip() for i in raw if str(i).strip()}) if isinstance(raw,list) else []
        missing=[c for c in required if c not in contexts]
        for c in missing: missing_by[c].append(sha or f'pr:{pr}')
        normalized.append({'pr_number':pr,'sha':sha,'contexts':contexts,'missing_required_contexts':missing})
    count=len(normalized); materialization=[]
    for c in required:
        missing=missing_by[c]; present=count-len(missing); materialization.append({'context':c,'sample_count':count,'present_count':present,'missing_count':len(missing),'materialization_rate':round(present/count,4) if count else 0.0,'missing_on':missing})
    if not inconclusive and any(i['missing_count'] for i in materialization): decision='required_checks_missing_on_samples'
    ts=observed_at or datetime.now(UTC)
    return {'schema_version':'1.0.0','contract':'reqsys-required-checks-materialization','observed_at':ts.astimezone(UTC).isoformat(),'decision':decision,'inconclusive':inconclusive,'required_contexts':required,'sample_count':count,'materialization':materialization,'samples':normalized,'automatic_branch_protection_change_allowed':False,'automatic_context_removal_allowed':False,'production_touched':False}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--protection',type=Path,required=True); p.add_argument('--samples',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--strict',action='store_true'); a=p.parse_args(); report=evaluate_materialization(protection_payload=load_object(a.protection),samples_payload=load_object(a.samples)); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(report,ensure_ascii=False)); blocking=report['inconclusive'] or report['decision']!='required_checks_materialized'; return 1 if a.strict and blocking else 0
if __name__=='__main__': raise SystemExit(main())
