#!/usr/bin/env python3
"""Evidence and governance helpers for the free-tier ReqSys backup workflow."""
from __future__ import annotations
import argparse, hashlib, json, sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ENVS={"dev","stg","prod"}; CRITS={"low","medium","high","critical"}
REQ={"id","environment","github_environment","fly_app","criticality","enabled","rpo_target_minutes","rto_target_seconds","rollout_state"}

def read(path: Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def write(path: Path,payload: Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def now()->str: return datetime.now(UTC).replace(microsecond=0).isoformat()
def sha(path: Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def manifest(path: Path)->dict[str,Any]:
    if not path.is_file(): raise FileNotFoundError(path)
    with sqlite3.connect(f"file:{path}?mode=ro",uri=True) as c:
        quick=str(c.execute("PRAGMA quick_check").fetchone()[0]); counts={}
        names=c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for (name,) in names:
            q=str(name).replace('"','""'); counts[str(name)]=int(c.execute(f'SELECT COUNT(*) FROM "{q}"').fetchone()[0])
    return {"path":str(path),"size_bytes":path.stat().st_size,"sha256":sha(path),"quick_check":quick,"table_counts":counts,"table_count":len(counts),"row_count_total":sum(counts.values())}

def validate_inventory(p:dict[str,Any])->list[str]:
    e=[]; storage=p.get("storage"); defaults=p.get("defaults"); assets=p.get("assets")
    if p.get("schema_version")!="1.0.0": e.append("schema_version must be 1.0.0")
    if not isinstance(storage,dict): e.append("storage must be an object")
    if not isinstance(defaults,dict): e.append("defaults must be an object")
    if not isinstance(assets,list) or not assets: return e+["assets must be a non-empty array"]
    ids=set(); envs=set()
    for i,a in enumerate(assets):
        if not isinstance(a,dict): e.append(f"assets[{i}] must be an object"); continue
        missing=REQ-set(a)
        if missing: e.append(f"assets[{i}] missing fields: {', '.join(sorted(missing))}"); continue
        if a["id"] in ids: e.append(f"duplicate asset id: {a['id']}")
        ids.add(a["id"]); envs.add(a["environment"])
        if a["environment"] not in ENVS: e.append(f"assets[{i}].environment invalid")
        if a["criticality"] not in CRITS: e.append(f"assets[{i}].criticality invalid")
        if not isinstance(a["enabled"],bool): e.append(f"assets[{i}].enabled must be boolean")
        if not str(a["fly_app"]).startswith("reqsys-api"): e.append(f"assets[{i}].fly_app outside allowlist")
        for k in ("rpo_target_minutes","rto_target_seconds"):
            if not isinstance(a[k],int) or a[k]<=0: e.append(f"assets[{i}].{k} must be positive")
    if envs!=ENVS: e.append("inventory must contain exactly dev, stg and prod")
    if isinstance(storage,dict):
        w,h=storage.get("free_tier_warn_bytes"),storage.get("free_tier_hard_bytes")
        if not isinstance(w,int) or not isinstance(h,int) or not 0<w<h: e.append("free-tier quota thresholds invalid")
    return e

def merged(p:dict[str,Any],a:dict[str,Any])->dict[str,Any]:
    d=dict(p.get("defaults",{})); r=dict(d.pop("retention",{})); out={**d,**a}; out["retention"]={**r,**a.get("retention",{})}; return out
def select(p:dict[str,Any],target:str,include_disabled:bool)->list[dict[str,Any]]:
    return [merged(p,a) for a in p["assets"] if (target=="all" or a["environment"]==target) and (a["enabled"] or include_disabled)]
def quota(total:int,warn:int,hard:int)->dict[str,Any]:
    status="critical" if total>=hard else "warning" if total>=warn else "healthy"
    return {"status":status,"total_size_bytes":total,"warn_bytes":warn,"hard_bytes":hard,"utilization_percent":round(total/hard*100,3)}
def restic_size(p:Any)->int:
    if isinstance(p,dict):
        for k in ("total_size","total_blob_size","total_uncompressed_size"):
            if isinstance(p.get(k),int): return p[k]
    raise ValueError("restic stats JSON missing total size")
def public(m:dict[str,Any])->dict[str,Any]:
    counts=m.get("table_counts",{}); canonical=json.dumps(counts,sort_keys=True,separators=(",",":"))
    return {"size_bytes":m.get("size_bytes"),"sha256":m.get("sha256"),"quick_check":m.get("quick_check"),"table_count":m.get("table_count",len(counts)),"row_count_total":m.get("row_count_total"),"table_counts_sha256":hashlib.sha256(canonical.encode()).hexdigest()}
def iso(value:str)->datetime: return datetime.fromisoformat(value.replace("Z","+00:00"))

def evidence(asset:dict[str,Any],source:dict[str,Any],restored:dict[str,Any],q:dict[str,Any],snapshot_id:str,run_url:str,correlation_id:str,started_at:str,completed_at:str,rto:float)->dict[str,Any]:
    match=source.get("quick_check")==restored.get("quick_check")=="ok" and source.get("sha256")==restored.get("sha256") and source.get("table_counts")==restored.get("table_counts")
    try: rpo=max(0.0,(iso(completed_at)-iso(str(source.get("generated_at")))).total_seconds()/60)
    except (TypeError,ValueError): rpo=0.0
    passed=match and rpo<=asset["rpo_target_minutes"] and rto<=asset["rto_target_seconds"] and q["status"]!="critical"
    return {"schema_version":"1.0.0","control_id":"BACEN-04","evidence_class":"real_asset_external_encrypted_backup_restore","asset_id":asset["id"],"environment":asset["environment"],"fly_app":asset["fly_app"],"database_engine":asset["database_engine"],"storage_provider":"cloudflare-r2","encryption":"restic-client-side","snapshot_id":snapshot_id,"backup_started_at":started_at,"restore_completed_at":completed_at,"rpo_minutes":round(rpo,6),"rpo_target_minutes":asset["rpo_target_minutes"],"rto_seconds":round(rto,6),"rto_target_seconds":asset["rto_target_seconds"],"integrity_match":match,"source_manifest":public(source),"restored_manifest":public(restored),"quota":q,"production_read_only":asset["environment"]=="prod","production_restore_claimed":False,"correlation_id":correlation_id,"run_url":run_url,"result":"passed" if passed else "failed","generated_at":now()}

def dashboard(inv:dict[str,Any],items:list[dict[str,Any]],configured:bool,missing:list[str],run_url:str,execution_result:str)->dict[str,Any]:
    by={x.get("asset_id"):x for x in items}; rows=[]
    for raw in inv["assets"]:
        a=merged(inv,raw); item=by.get(a["id"])
        status=("healthy" if item.get("result")=="passed" else "critical") if item else "blocked_configuration" if a["enabled"] and not configured else "critical" if a["enabled"] and execution_result in {"failure","cancelled"} else "pending_execution" if a["enabled"] else "rollout_pending"
        rows.append({"asset_id":a["id"],"environment":a["environment"],"fly_app":a["fly_app"],"enabled":a["enabled"],"rollout_state":a["rollout_state"],"status":status,"result":item.get("result") if item else None,"integrity_match":item.get("integrity_match") if item else None,"rpo_minutes":item.get("rpo_minutes") if item else None,"rto_seconds":item.get("rto_seconds") if item else None,"snapshot_id":item.get("snapshot_id") if item else None,"quota":item.get("quota") if item else None,"correlation_id":item.get("correlation_id") if item else None})
    health="critical" if any(x["status"]=="critical" for x in rows) else "warning" if any(x["status"]!="healthy" for x in rows) else "healthy"
    return {"schema_version":"1.0.0","control_id":"BACEN-04","health":health,"generated_at":now(),"external_storage_configured":configured,"missing_secrets":missing,"run_url":run_url,"execution_result":execution_result,"assets":rows}

def markdown(d:dict[str,Any])->str:
    icon={"healthy":"🟢","warning":"🟡","critical":"🔴"}[d["health"]]; lines=[f"# {icon} Dashboard BACEN-04 — Cobertura real de backup","",f"> Atualizado automaticamente em `{d['generated_at']}`.","",f"- Armazenamento externo configurado: **{str(d['external_storage_configured']).lower()}**"]
    if d["missing_secrets"]: lines.append(f"- Configuração pendente: `{', '.join(d['missing_secrets'])}`")
    lines += ["","| Ambiente | Ativo | Estado | Resultado | Integridade | RPO | RTO | Rollout |","|---|---|---|---|---|---:|---:|---|"]
    for x in d["assets"]: lines.append(f"| {x['environment'].upper()} | `{x['asset_id']}` | **{x['status']}** | `{x['result'] or '—'}` | `{'sim' if x['integrity_match'] is True else '—'}` | `{str(x['rpo_minutes'])+' min' if x['rpo_minutes'] is not None else '—'}` | `{str(x['rto_seconds'])+' s' if x['rto_seconds'] is not None else '—'}` | {x['rollout_state']} |")
    return "\n".join(lines+["","## Guard rails gratuitos","","- dumps nunca são gravados no repositório ou na issue;","- criptografia ocorre no cliente antes do armazenamento externo;","- quota alerta em 8 GiB e bloqueia em 9 GiB;","- PROD permanece desabilitado até evidência válida em DEV e STG;","- restaurações ocorrem fora do ambiente de origem.","",f"[Abrir execução]({d['run_url']})",""])
def card(d:dict[str,Any])->dict[str,Any]:
    color={"healthy":"Good","warning":"Warning","critical":"Attention"}[d["health"]]
    return {"$schema":"http://adaptivecards.io/schemas/adaptive-card.json","type":"AdaptiveCard","version":"1.2","msteams":{"width":"Full"},"body":[{"type":"TextBlock","text":"ReqSys — cobertura real de backup","weight":"Bolder","size":"Large","color":color,"wrap":True},{"type":"TextBlock","text":f"Saúde: {d['health']}","wrap":True},{"type":"FactSet","facts":[{"title":x["environment"].upper(),"value":f"{x['status']} · {x['asset_id']}"} for x in d["assets"]]}],"actions":[{"type":"Action.OpenUrl","title":"Abrir execução","url":d["run_url"]}]}

def main()->int:
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
    v=s.add_parser("validate"); v.add_argument("--inventory",type=Path,required=True)
    m=s.add_parser("matrix"); m.add_argument("--inventory",type=Path,required=True); m.add_argument("--target",choices=["dev","stg","prod","all"],default="all"); m.add_argument("--include-disabled",action="store_true")
    f=s.add_parser("manifest"); f.add_argument("--database",type=Path,required=True); f.add_argument("--output",type=Path,required=True)
    q=s.add_parser("quota"); q.add_argument("--stats",type=Path,required=True); q.add_argument("--warn",type=int,required=True); q.add_argument("--hard",type=int,required=True); q.add_argument("--output",type=Path,required=True)
    e=s.add_parser("evidence");
    for name in ("asset","source","restored","quota","output"): e.add_argument(f"--{name}",type=Path,required=True)
    for name in ("snapshot-id","run-url","correlation-id","started-at","completed-at"): e.add_argument(f"--{name}",required=True)
    e.add_argument("--rto",type=float,required=True)
    d=s.add_parser("dashboard"); d.add_argument("--inventory",type=Path,required=True); d.add_argument("--evidence-dir",type=Path,required=True); d.add_argument("--configured",action="store_true"); d.add_argument("--missing",default=""); d.add_argument("--run-url",required=True); d.add_argument("--execution-result",default="unknown"); d.add_argument("--json",type=Path,required=True); d.add_argument("--markdown",type=Path,required=True); d.add_argument("--card",type=Path,required=True)
    a=p.parse_args()
    if a.cmd=="validate":
        errors=validate_inventory(read(a.inventory)); print("\n".join(errors) if errors else "inventory valid"); return bool(errors)
    if a.cmd=="matrix":
        inv=read(a.inventory); errors=validate_inventory(inv)
        if errors: raise SystemExit("; ".join(errors))
        print(json.dumps({"include":select(inv,a.target,a.include_disabled)},separators=(",",":"))); return 0
    if a.cmd=="manifest": write(a.output,manifest(a.database)); return 0
    if a.cmd=="quota":
        out=quota(restic_size(read(a.stats)),a.warn,a.hard); write(a.output,out); print(out["status"]); return 2 if out["status"]=="critical" else 0
    if a.cmd=="evidence":
        out=evidence(read(a.asset),read(a.source),read(a.restored),read(a.quota),a.snapshot_id,a.run_url,a.correlation_id,a.started_at,a.completed_at,a.rto); write(a.output,out); print(out["result"]); return out["result"]!="passed"
    items=[read(x) for x in a.evidence_dir.rglob("evidence.json")] if a.evidence_dir.is_dir() else []
    out=dashboard(read(a.inventory),items,a.configured,[x for x in a.missing.split(",") if x],a.run_url,a.execution_result); write(a.json,out); a.markdown.parent.mkdir(parents=True,exist_ok=True); a.markdown.write_text(markdown(out),encoding="utf-8"); write(a.card,card(out)); return 0
if __name__=="__main__": raise SystemExit(main())
