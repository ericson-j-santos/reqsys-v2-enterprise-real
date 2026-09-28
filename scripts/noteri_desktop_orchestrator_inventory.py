#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, socket, time
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any

SOURCE="Noteri"; TARGET="DESKTOP-PDQK954"; PORT=8787
TASK="host.inventory.files.v1"; SCOPE="reqsys-control-plane"
CONFIRM="INVENTORY-DESKTOP-CONTROL-PLANE"
TERMINAL={"CONCLUÍDO","BLOQUEADO","CANCELADO"}

class ProbeError(RuntimeError): pass

def req(method:str,path:str,payload:dict[str,Any]|None=None,timeout:float=5.0):
    if path not in {"/readyz","/v1/workers","/v1/intake"} and not path.startswith("/v1/work-items/"):
        raise ProbeError("path_not_allowlisted")
    body=None; headers={"Accept":"application/json","Cache-Control":"no-store"}
    if payload is not None:
        body=json.dumps(payload,sort_keys=True).encode(); headers["Content-Type"]="application/json"
    c=HTTPConnection(TARGET,PORT,timeout=timeout)
    try:
        c.request(method,path,body=body,headers=headers); r=c.getresponse()
        raw=r.read(262144).decode("utf-8","replace"); data=json.loads(raw) if raw else {}
        if not isinstance(data,dict): raise ProbeError("invalid_payload")
        return int(r.status),data
    except (OSError,HTTPException,TimeoutError) as e:
        raise ProbeError("control_plane_unavailable") from e
    finally: c.close()

def run(confirm:str, correlation_id:str, evidence:Path):
    if confirm!=CONFIRM: raise ProbeError("confirmation_invalid")
    if os.name!="nt" or socket.gethostname().casefold()!=SOURCE.casefold(): raise ProbeError("source_host_invalid")
    s,p=req("GET","/readyz")
    if s!=200 or p.get("ready") is not True: raise ProbeError("orchestrator_not_ready")
    s,p=req("GET","/v1/workers"); workers=p.get("workers")
    if s!=200 or not isinstance(workers,list): raise ProbeError("worker_registry_invalid")
    matches=[w for w in workers if isinstance(w,dict) and str(w.get("device_name") or "").casefold()==TARGET.casefold()]
    if len(matches)!=1: raise ProbeError("desktop_worker_not_unique")
    caps=(matches[0].get("capabilities") or {}).get("safe_task_types") or []
    if TASK not in caps: raise ProbeError("inventory_capability_missing")
    digest=hashlib.sha256(f"{TASK}|{TARGET}|{SCOPE}|{correlation_id}".encode()).hexdigest()
    body={"event_id":f"evt-inventory-{digest[:32]}","correlation_id":correlation_id,
          "idempotency_key":f"desktop-inventory:{digest}","task_type":TASK,
          "payload":{"target_host":TARGET,"scope":SCOPE},"risk":1,"max_attempts":1,"lease_seconds":45}
    s,p=req("POST","/v1/intake",body)
    if s not in {200,201}: raise ProbeError(f"intake_http_{s}")
    item=p.get("item") or {}; item_id=item.get("id")
    if not isinstance(item_id,str): raise ProbeError("intake_invalid")
    deadline=time.monotonic()+45; term=None
    while time.monotonic()<deadline:
        rs,rp=req("GET",f"/v1/work-items/{item_id}")
        obj=rp.get("item") if isinstance(rp,dict) else None
        if rs==200 and isinstance(obj,dict) and str(obj.get("status") or "") in TERMINAL:
            term=obj; break
        time.sleep(.5)
    if term is None: raise ProbeError("inventory_timeout")
    if term.get("status")!="CONCLUÍDO": raise ProbeError(f"inventory_terminal_{term.get('status')}")
    result=term.get("result")
    if not isinstance(result,dict) or result.get("handler")!=TASK: raise ProbeError("inventory_result_invalid")
    out={"ok":True,"result":"DESKTOP_CONTROL_PLANE_INVENTORY_COMPLETED","source_host":SOURCE,"target_host":TARGET,
         "task_type":TASK,"correlation_id":correlation_id,"work_item_id":item_id,
         "match_count":result.get("match_count"),"matches":result.get("matches") or [],
         "roots_checked":result.get("roots_checked") or [],"truncated":bool(result.get("truncated")),
         "file_contents_read":bool(result.get("file_contents_read")),"secrets_read":bool(result.get("secrets_read")),
         "production_touched":bool(result.get("production_touched"))}
    evidence.parent.mkdir(parents=True,exist_ok=True); evidence.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,sort_keys=True)); return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--confirm",required=True); ap.add_argument("--correlation-id",required=True); ap.add_argument("--evidence-file",type=Path,required=True)
    a=ap.parse_args()
    try: return run(a.confirm,a.correlation_id,a.evidence_file.resolve())
    except ProbeError as e:
        out={"ok":False,"result":"DESKTOP_CONTROL_PLANE_INVENTORY_BLOCKED","reason":str(e)[:160],"source_host":SOURCE,"target_host":TARGET,"task_type":TASK}
        a.evidence_file.parent.mkdir(parents=True,exist_ok=True); a.evidence_file.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(out)); return 2
if __name__=="__main__": raise SystemExit(main())
