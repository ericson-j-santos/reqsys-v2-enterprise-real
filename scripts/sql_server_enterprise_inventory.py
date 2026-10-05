#!/usr/bin/env python3
"""Inventário SQL Server somente leitura para o enterprise validation gate."""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path
READ_ONLY_SQL="""SET NOCOUNT ON;
SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) product_version,CAST(SERVERPROPERTY('ProductLevel') AS nvarchar(128)) product_level,CAST(SERVERPROPERTY('ProductUpdateLevel') AS nvarchar(128)) product_update_level,CAST(SERVERPROPERTY('Edition') AS nvarchar(256)) edition,CAST(SERVERPROPERTY('EngineEdition') AS int) engine_edition,CAST(SERVERPROPERTY('IsHadrEnabled') AS int) is_hadr_enabled;
SELECT name,compatibility_level,is_query_store_on,snapshot_isolation_state_desc,is_read_committed_snapshot_on,is_accelerated_database_recovery_on FROM sys.databases WHERE name=DB_NAME();
SELECT actual_state_desc,desired_state_desc,readonly_reason,current_storage_size_mb,max_storage_size_mb FROM sys.database_query_store_options;
SELECT CASE WHEN ISJSON(N'{"gate":true}')=1 THEN 1 ELSE 0 END isjson_available,CASE WHEN CAST(SERVERPROPERTY('ProductMajorVersion') AS int)>=13 THEN 1 ELSE 0 END openjson_capable;"""
def utcnow(): return datetime.now(timezone.utc).isoformat()
def connect(server,database):
 import pyodbc
 candidates=[d for d in ("ODBC Driver 18 for SQL Server","ODBC Driver 17 for SQL Server") if d in pyodbc.drivers()]
 if not candidates: raise RuntimeError("sql_server_odbc_driver_not_found")
 last=None
 for d in candidates:
  try:
   cs=f"Driver={{{d}}};Server={server};Database={database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;"
   return pyodbc.connect(cs,timeout=15,autocommit=True),d
  except Exception as exc: last=exc
 raise RuntimeError("integrated_read_only_connection_failed") from last
def rows(cur):
 cols=[c[0] for c in cur.description]; return [dict(zip(cols,r)) for r in cur.fetchall()]
def collect(server,database):
 import pyodbc
 conn,driver=connect(server,database)
 try:
  cur=conn.cursor(); cur.execute(READ_ONLY_SQL); sets=[]
  while True:
   if cur.description: sets.append(rows(cur))
   if not cur.nextset(): break
  if len(sets)!=4: raise RuntimeError("unexpected_inventory_result_sets")
  return {"status":"passed","captured_at":utcnow(),"server":server,"database":database,"connection_mode":"integrated_read_only","odbc_driver":driver,"installed_sql_drivers":[d for d in pyodbc.drivers() if "SQL Server" in d],"server_properties":sets[0][0],"database_properties":sets[1][0],"query_store":sets[2][0] if sets[2] else None,"json_capabilities":sets[3][0],"secret_exposed":False}
 finally: conn.close()
def main():
 p=argparse.ArgumentParser(); p.add_argument("--server",default=os.getenv("REQSYS_SQLSERVER_HOST","localhost")); p.add_argument("--database",default=os.getenv("REQSYS_SQLSERVER_DB","ReqSysIntegrationDev")); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
 try: payload=collect(a.server,a.database); code=0
 except Exception as exc: payload={"status":"blocked","captured_at":utcnow(),"server":a.server,"database":a.database,"error":exc.__class__.__name__,"secret_exposed":False}; code=2
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8"); print(json.dumps({k:payload.get(k) for k in ("status","server","database","error")},ensure_ascii=False)); return code
if __name__=="__main__": raise SystemExit(main())
