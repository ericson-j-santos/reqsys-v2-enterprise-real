#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SQL_DIR=ROOT/"backend"/"app"/"services"/"movimento_email"/"sql"/"source_dev"

def safe(value:str)->str:
    if not re.fullmatch(r"[A-Za-z0-9_]+",value):
        raise SystemExit("nome de banco inválido")
    return value

def connect(server:str,database:str,autocommit:bool=False):
    import pyodbc
    return pyodbc.connect(
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};Database={database};"
        "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
        timeout=10,autocommit=autocommit)

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--server",default="localhost")
    p.add_argument("--database",default="ReqSysMovimentoSourceDev")
    p.add_argument("--seed-e2e",action="store_true")
    a=p.parse_args()
    db=safe(a.database)

    master=connect(a.server,"master",True)
    try:
        master.cursor().execute(f"IF DB_ID('{db}') IS NULL CREATE DATABASE [{db}]")
    finally:
        master.close()

    conn=connect(a.server,db)
    try:
        cur=conn.cursor()
        cur.execute((SQL_DIR/"V1__legacy_source_schema.sql").read_text(encoding="utf-8"))
        if a.seed_e2e:
            cur.execute((SQL_DIR/"V1__seed_e2e.sql").read_text(encoding="utf-8"))
        conn.commit()
        tables={}
        for name in ("fechamento_diario","pendencias_cadastro","pendencias_historicas","pendencias_observacao"):
            cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='legacy_ssrs' AND TABLE_NAME=?",name)
            tables[name]=int(cur.fetchone()[0])==1
        ok=all(tables.values())
        print(json.dumps({"status":"validated" if ok else "failed","server":a.server,"database":db,"schema":"legacy_ssrs","tables":tables,"seed_e2e":a.seed_e2e,"secrets_used":False,"corporate_source_validated":False},ensure_ascii=False))
        return 0 if ok else 3
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__=="__main__":
    raise SystemExit(main())
