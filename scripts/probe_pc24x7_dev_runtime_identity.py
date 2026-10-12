#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from urllib.error import HTTPError,URLError
from urllib.request import HTTPRedirectHandler,ProxyHandler,Request,build_opener
BASE="http://127.0.0.1:8210"; LIMIT=262144; TIMEOUT=4
ROUTES=("/api/runtime/version","/api/runtime/health","/api/runtime/readiness","/api/runtime/liveness","/api/runtime/build-info","/api/runtime/dependencies")
SHA=re.compile(r"^[0-9a-f]{40}$")
class ProbeError(RuntimeError): pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): return None
def data(payload):
 if not isinstance(payload,dict): raise ProbeError("malformed_payload")
 value=payload.get("data",payload)
 if not isinstance(value,dict): raise ProbeError("malformed_envelope")
 return value
def get(path,opener=None):
 if path not in ROUTES: raise ProbeError("route_not_allowlisted")
 client=opener or build_opener(ProxyHandler({}),NoRedirect())
 req=Request(BASE+path,headers={"Accept":"application/json","User-Agent":"reqsys-dev-identity-probe/1.0"},method="GET")
 try:
  with client.open(req,timeout=TIMEOUT) as response:
   if int(response.status)!=200: raise ProbeError("unexpected_http_status")
   raw=response.read(LIMIT+1)
 except HTTPError as exc:
  if 300<=int(exc.code)<400: raise ProbeError("redirect_refused") from exc
  raise ProbeError("http_error") from exc
 except (URLError,TimeoutError,OSError) as exc: raise ProbeError("transport_error") from exc
 if len(raw)>LIMIT: raise ProbeError("payload_too_large")
 try: return data(json.loads(raw.decode("utf-8")))
 except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise ProbeError("malformed_json") from exc
def common(value):
 item={k:value[k] for k in ("service","version","environment","check") if isinstance(value.get(k),(str,bool,int,float))}
 if "status" in value:
  if isinstance(value["status"],str):item["status"]=value["status"]
  else:item["status_invalid_type"]=True
 if "alive" in value:
  if type(value["alive"]) is bool:item["alive"]=value["alive"]
  else:item["alive_invalid_type"]=True
 return item
def run(expected_sha,opener=None):
 version=get(ROUTES[0],opener)
 if version.get("service")!="reqsys-api" or str(version.get("environment","")).casefold()!="desenvolvimento": raise ProbeError("dev_identity_mismatch")
 result={"schema_version":"1.0","base":"http://127.0.0.1:8210","identity_validated":True,"expected_sha":expected_sha,"routes":{ROUTES[0]:common(version)}}
 for path in ROUTES[1:]:
  value=get(path,opener); item=common(value)
  if value.get("service") not in (None,"reqsys-api"): raise ProbeError("service_identity_mismatch")
  if path=="/api/runtime/build-info":
   observed=str(value.get("build_sha","")).casefold(); item["build_sha"]=observed if SHA.fullmatch(observed) else "unknown"
   item["runtime_sha_verified"]=bool(SHA.fullmatch(observed) and observed==expected_sha.casefold())
  elif path=="/api/runtime/readiness": item["readiness_scope"]="superficial"
  elif path=="/api/runtime/dependencies":
   deps=value.get("dependencies",[]); item["dependencies"]=[]
   if isinstance(deps,list):
    for dep in deps:
     if isinstance(dep,dict): item["dependencies"].append({k:dep[k] for k in ("name","status","required") if isinstance(dep.get(k),(str,bool))})
  result["routes"][path]=item
 return result
def main():
 parser=argparse.ArgumentParser(); parser.add_argument("--expected-sha",required=True); args=parser.parse_args()
 if not SHA.fullmatch(args.expected_sha.casefold()): print(json.dumps({"status":"blocked","reason":"invalid_expected_sha"})); return 2
 try: output=run(args.expected_sha)
 except ProbeError as exc: print(json.dumps({"status":"blocked","reason":str(exc)},sort_keys=True)); return 2
 print(json.dumps({"status":"probe_complete",**output},sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
