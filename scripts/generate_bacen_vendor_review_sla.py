#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import UTC, datetime
from pathlib import Path
import yaml
APPROVED={'approved','signed','complete','validated'}
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--register',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 data=yaml.safe_load(a.register.read_text(encoding='utf-8'))
 vendors=(data.get('providers') or data.get('vendors') or []) if isinstance(data,dict) else []
 if not isinstance(vendors,list) or not vendors: raise ValueError('registro de terceiros inválido')
 seen=set(); compliant=[]; overdue=[]; errors=[]
 for item in vendors:
  if not isinstance(item,dict) or not item.get('id'): errors.append('vendor_without_id'); continue
  vid=str(item['id'])
  if vid in seen: errors.append(f'duplicate_vendor:{vid}')
  seen.add(vid)
  status=str(item.get('risk_review_status','missing')).lower()
  (compliant if status in APPROVED else overdue).append(vid)
 report={'schema_version':'1.0.0','control_id':'BACEN-05','generated_at':datetime.now(UTC).isoformat(),'source_sha256':hashlib.sha256(a.register.read_bytes()).hexdigest(),'review_cycle_days':30,'summary':{'vendors':len(seen),'within_sla':len(compliant),'pending_or_overdue':len(overdue)},'within_sla_vendor_ids':sorted(compliant),'pending_or_overdue_vendor_ids':sorted(overdue),'control_status':'implemented' if seen and not overdue and not errors else 'partial','automatic_blocking':bool(errors),'errors':sorted(errors),'human_action_required':bool(overdue),'production_touched':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return 1 if report['automatic_blocking'] else 0
if __name__=='__main__': raise SystemExit(main())
