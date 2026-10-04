#!/usr/bin/env python3
"""SLO, error budget e degradação sustentada para performance do ReqSys."""
from __future__ import annotations
import argparse, json, statistics, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
VERSION = "1.0.0"
API_HIGHER_WORSE = ("p95_ms", "p99_ms")
BROWSER_HIGHER_WORSE = ("event_loop_lag_p95_ms","event_loop_lag_max_ms","max_long_task_ms","lcp_ms","heap_after_gc_mb","gc_roundtrip_ms")

def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")); return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
def _median(values: list[float]) -> float|None: return None if not values else float(statistics.median(values))
def _increase_percent(current: float, baseline: float) -> float|None: return None if baseline <= 0 else ((current-baseline)/baseline)*100.0
def _drop_percent(current: float, baseline: float) -> float|None: return None if baseline <= 0 else ((baseline-current)/baseline)*100.0

def _policy_endpoints(policy: dict[str, Any]) -> dict[str, dict[str,float]]:
    out={}
    for item in policy.get("endpoints") or []:
        path=str(item.get("path") or ""); budget=item.get("budget") or {}
        if path:
            out[path]={"max_p95_ms":float(budget.get("max_p95_ms",float("inf"))),"max_p99_ms":float(budget.get("max_p99_ms",float("inf"))),"max_error_rate_percent":float(budget.get("max_error_rate_percent",100.0)),"min_throughput_rps":float(budget.get("min_throughput_rps",0.0))}
    return out

def _browser_budget(policy: dict[str, Any]) -> dict[str,float]:
    raw=policy.get("browser") or {}
    return {"event_loop_lag_p95_ms":float(raw.get("max_event_loop_lag_p95_ms",float("inf"))),"event_loop_lag_max_ms":float(raw.get("max_event_loop_lag_max_ms",float("inf"))),"max_long_task_ms":float(raw.get("max_long_task_ms",float("inf"))),"lcp_ms":float(raw.get("max_lcp_ms",float("inf"))),"heap_after_gc_mb":float(raw.get("max_heap_after_gc_mb",float("inf"))),"gc_roundtrip_ms":float(raw.get("max_gc_roundtrip_ms",float("inf")))}

def _window_snapshots(snapshots,current,window_days):
    current_at=parse_iso(str(current["observed_at"])); cutoff=current_at-timedelta(days=window_days)
    return sorted([i for i in snapshots if i.get("observed_at") and cutoff<=parse_iso(str(i["observed_at"]))<=current_at],key=lambda i:parse_iso(str(i["observed_at"])))

def _slo_record(*,slo_id,name,target_percent,window_days,good,total,mature,environment,warning_remaining_percent):
    actual=None if total<=0 else round((good/total)*100.0,4)
    base={"slo_id":slo_id,"name":name,"environment":environment,"target_percent":target_percent,"window_days":window_days,"actual_percent":actual,"eligible_measurements":total,"good_measurements":good,"bad_measurements":max(0,total-good),"mature":mature}
    if not mature or actual is None:
        return {**base,"error_budget_remaining":None,"error_budget_total_pp":round(100-target_percent,4),"error_budget_consumed_pp":None,"error_budget_consumed_percent":None,"error_budget_remaining_percent":None,"breach":False,"warning":False,"status":"no_data"}
    allowed=max(0.0,100-target_percent); consumed=max(0.0,100-actual); remaining=actual-target_percent
    consumed_pct=(100.0 if consumed>0 else 0.0) if allowed<=0 else (consumed/allowed)*100.0
    remaining_pct=max(0.0,100.0-consumed_pct); breach=actual<target_percent; warning=(not breach and remaining_pct<=warning_remaining_percent)
    return {**base,"error_budget_remaining":round(remaining,4),"error_budget_total_pp":round(allowed,4),"error_budget_consumed_pp":round(consumed,4),"error_budget_consumed_percent":round(consumed_pct,2),"error_budget_remaining_percent":round(remaining_pct,2),"breach":breach,"warning":warning,"status":"breach" if breach else "met"}

def build_slos(history_report,policy,*,environment):
    sp=policy.get("performance_slo") or {}; window=int(sp.get("window_days",7)); minimum=int(sp.get("minimum_samples",5)); warning=float(sp.get("error_budget_warning_remaining_percent",25)); targets=sp.get("targets") or {}
    snapshots=history_report.get("snapshots") or []; current=history_report.get("current") or (snapshots[-1] if snapshots else None); window_samples=[] if not current else _window_snapshots(snapshots,current,window); mature=len(window_samples)>=minimum
    eps=_policy_endpoints(policy); blimits=_browser_budget(policy); lg=lt=rg=rt=cg=ct=bg=bt=0
    for snap in window_samples:
        api=snap.get("api") or {}
        for path,budget in eps.items():
            m=api.get(path)
            if not isinstance(m,dict): continue
            if m.get("p95_ms") is not None and m.get("p99_ms") is not None:
                lt+=1; lg+= int(float(m["p95_ms"])<=budget["max_p95_ms"] and float(m["p99_ms"])<=budget["max_p99_ms"])
            if m.get("error_rate_percent") is not None:
                rt+=1; rg+= int(float(m["error_rate_percent"])<=budget["max_error_rate_percent"])
            if m.get("throughput_rps") is not None:
                ct+=1; cg+= int(float(m["throughput_rps"])>=budget["min_throughput_rps"])
        browser=snap.get("browser") or {}; available=[k for k in blimits if browser.get(k) is not None]
        if available:
            bt+=1; bg+=int(all(float(browser[k])<=blimits[k] for k in available))
    specs=(("performance_api_latency","Performance API — latência p95/p99",float(targets.get("api_latency_good_percent",95)),lg,lt),("performance_api_reliability","Performance API — taxa de erro",float(targets.get("api_reliability_good_percent",99)),rg,rt),("performance_api_capacity","Performance API — throughput",float(targets.get("api_capacity_good_percent",95)),cg,ct),("performance_browser_runtime","Performance frontend — runtime browser",float(targets.get("browser_runtime_good_percent",95)),bg,bt))
    return [_slo_record(slo_id=i,name=n,target_percent=t,window_days=window,good=g,total=tot,mature=mature,environment=environment,warning_remaining_percent=warning) for i,n,t,g,tot in specs]

def _reference_baseline(reference,current):
    paths=set((current.get("api") or {}).keys())
    for s in reference: paths.update((s.get("api") or {}).keys())
    api={}
    for path in sorted(paths):
        api[path]={m:_median([float(s["api"][path][m]) for s in reference if path in (s.get("api") or {}) and s["api"][path].get(m) is not None]) for m in ("p95_ms","p99_ms","throughput_rps","error_rate_percent")}
    browser={m:_median([float(s["browser"][m]) for s in reference if (s.get("browser") or {}).get(m) is not None]) for m in BROWSER_HIGHER_WORSE}
    return {"api":api,"browser":browser}

def detect_sustained_degradation(history_report,policy):
    sp=policy.get("performance_slo") or {}; sd=sp.get("sustained_degradation") or {}; required=int(sd.get("required_consecutive",3)); rw=int(sd.get("reference_window_days",7)); minref=int(sd.get("minimum_reference_samples",5)); rp=(policy.get("history") or {}).get("regression") or {}; lat=float(rp.get("max_latency_increase_percent",30)); thr=float(rp.get("max_throughput_drop_percent",30)); err=float(rp.get("max_error_rate_increase_pp",1)); brow=float(rp.get("max_browser_metric_increase_percent",30))
    snaps=sorted(history_report.get("snapshots") or [],key=lambda i:parse_iso(str(i["observed_at"])))
    if len(snaps)<required+minref: return {"status":"insufficient_history","required_consecutive":required,"reference_window_days":rw,"reference_samples":max(0,len(snaps)-required),"minimum_reference_samples":minref,"findings":[]}
    trailing=snaps[-required:]; first=parse_iso(str(trailing[0]["observed_at"])); cutoff=first-timedelta(days=rw); ref=[i for i in snaps[:-required] if cutoff<=parse_iso(str(i["observed_at"]))<first]
    if len(ref)<minref: return {"status":"insufficient_history","required_consecutive":required,"reference_window_days":rw,"reference_samples":len(ref),"minimum_reference_samples":minref,"findings":[]}
    base=_reference_baseline(ref,trailing[-1]); findings=[]
    def add(scope,subject,metric,kind,values,b,threshold): findings.append({"scope":scope,"subject":subject,"metric":metric,"kind":kind,"required_consecutive":required,"observed_values":[round(v,4) for v in values],"baseline":round(b,4),"threshold":threshold,"run_ids":[str(i.get("run_id") or "") for i in trailing]})
    for path in sorted((trailing[-1].get("api") or {})):
        bm=(base["api"] or {}).get(path) or {}
        for metric in API_HIGHER_WORSE:
            b=bm.get(metric); values=[]; ok=b is not None
            if ok:
                for s in trailing:
                    m=(s.get("api") or {}).get(path) or {}; v=m.get(metric)
                    if v is None or (_increase_percent(float(v),float(b)) or 0)<=lat: ok=False; break
                    values.append(float(v))
            if ok: add("api",path,metric,"increase_percent",values,float(b),lat)
        b=bm.get("throughput_rps"); values=[]; ok=b is not None
        if ok:
            for s in trailing:
                m=(s.get("api") or {}).get(path) or {}; v=m.get("throughput_rps")
                if v is None or (_drop_percent(float(v),float(b)) or 0)<=thr: ok=False; break
                values.append(float(v))
        if ok: add("api",path,"throughput_rps","drop_percent",values,float(b),thr)
        b=bm.get("error_rate_percent"); values=[]; ok=b is not None
        if ok:
            for s in trailing:
                m=(s.get("api") or {}).get(path) or {}; v=m.get("error_rate_percent")
                if v is None or float(v)-float(b)<=err: ok=False; break
                values.append(float(v))
        if ok: add("api",path,"error_rate_percent","increase_points",values,float(b),err)
    for metric in BROWSER_HIGHER_WORSE:
        b=(base.get("browser") or {}).get(metric); values=[]; ok=b is not None
        if ok:
            for s in trailing:
                v=(s.get("browser") or {}).get(metric)
                if v is None or (_increase_percent(float(v),float(b)) or 0)<=brow: ok=False; break
                values.append(float(v))
        if ok: add("browser","frontend",metric,"increase_percent",values,float(b),brow)
    return {"status":"degraded" if findings else "stable","required_consecutive":required,"reference_window_days":rw,"reference_samples":len(ref),"minimum_reference_samples":minref,"findings":findings}

def build_report(*,history_report,policy,environment="prod",correlation_id=None):
    slos=build_slos(history_report,policy,environment=environment); sustained=detect_sustained_degradation(history_report,policy); mature=[s for s in slos if s.get("mature")]; breaches=[s for s in mature if s.get("breach")]; warnings=[s for s in mature if s.get("warning")]; points=history_report.get("regressions") or []
    if breaches or sustained.get("findings"): status,risk="blocked","high"
    elif warnings or points: status,risk="watch","medium"
    elif not mature: status,risk="insufficient_history","low"
    else: status,risk="passed","low"
    return {"schema_version":"1.0.0","slo_version":VERSION,"contract":"reqsys-performance-slo-error-budget","source":"performance-slo-error-budget","generated_at":datetime.now(UTC).isoformat().replace("+00:00","Z"),"environment":environment,"correlation_id":correlation_id or str(uuid4()),"policy_version":policy.get("policy_version","unknown"),"status":status,"operational_risk":risk,"mode":"strict_on_main","summary":{"slo_count":len(slos),"mature_slo_count":len(mature),"breach_count":len(breaches),"warning_count":len(warnings),"met_count":sum(1 for s in mature if s.get("status")=="met"),"no_data_count":sum(1 for s in slos if s.get("status")=="no_data"),"point_regressions_total":len(points),"sustained_degradations_total":len(sustained.get("findings") or [])},"slos":slos,"sustained_degradation":sustained,"point_regressions":points,"guardrails":["absolute_budgets_remain_authoritative","single_relative_regression_is_watch","three_consecutive_relative_regressions_block","error_budget_exhaustion_blocks"]}

def parse_args(argv=None):
    p=argparse.ArgumentParser(description="ReqSys performance SLO/error budget gate"); p.add_argument("--history",type=Path,default=Path("artifacts/performance/performance-history.json")); p.add_argument("--policy",type=Path,default=Path("config/runtime-performance-budgets.json")); p.add_argument("--output",type=Path,default=Path("artifacts/performance/performance-slo-evidence.json")); p.add_argument("--environment",default="prod"); p.add_argument("--correlation-id",default=""); p.add_argument("--strict",action="store_true"); return p.parse_args(argv)
def main(argv=None):
    a=parse_args(argv)
    try:
        h=json.loads(a.history.read_text(encoding="utf-8")); policy=json.loads(a.policy.read_text(encoding="utf-8")); report=build_report(history_report=h,policy=policy,environment=a.environment,correlation_id=a.correlation_id or None); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report["summary"],ensure_ascii=False)); return 1 if a.strict and report["status"]=="blocked" else 0
    except Exception as exc:
        print(f"performance_slo_error: {type(exc).__name__}: {exc}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
