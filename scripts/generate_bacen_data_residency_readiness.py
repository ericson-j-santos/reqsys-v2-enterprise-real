#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import UTC, datetime
from pathlib import Path
import yaml
APPROVED='formally_approved'
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 data=yaml.safe_load(a.manifest.read_text(encoding='utf-8'))
 vendors=data.get('vendors') if isinstance(data,dict) else None
 if not isinstance(vendors,list): raise ValueError('manifesto DPA inválido')
 seen=set(); approved=[]; pending=[]; errors=[]
 for item in vendors:
  if not isinstance(item,dict) or not item.get('id'): errors.append('vendor_without_id'); continue
  vid=str(item['id'])
  if vid in seen: errors.append(f'duplicate_vendor:{vid}')
  seen.add(vid)
  (approved if item.get('data_location')==APPROVED else pending).append(vid)
 report={'schema_version':'1.0.0','control_id':'BACEN-05','generated_at':datetime.now(UTC).isoformat(),'source_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),'summary':{'vendors':len(seen),'approved':len(approved),'pending':len(pending)},'approved_vendor_ids':sorted(approved),'pending_vendor_ids':sorted(pending),'control_status':'implemented' if seen and not pending and not errors else 'partial','automatic_blocking':bool(errors),'errors':sorted(errors),'human_action_required':bool(pending),'production_touched':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return 1 if report['automatic_blocking'] else 0
if __name__=='__main__': raise SystemExit(main())
