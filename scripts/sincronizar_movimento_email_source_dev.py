#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from datetime import date

TABLES={
 "fechamento_diario":("indicador,valor,observacao,data_referencia,source_tag",5),
 "pendencias_cadastro":("protocolo,cliente,cpf,pendencia,dias_em_aberto,responsavel,data_referencia,source_tag",8),
 "pendencias_historicas":("periodo_referencia,pendencia,quantidade,percentual,data_referencia,source_tag",6),
 "pendencias_observacao":("protocolo,tipo_inconsistencia,descricao,etapa,data_referencia,source_tag",6),
}

def safe(value:str)->str:
    if not re.fullmatch(r"[A-Za-z0-9_]+",value):
        raise SystemExit("identificador inválido")
    return value

def connect(server:str,database:str):
    import pyodbc
    return pyodbc.connect(
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={server};Database={database};"
        "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
        timeout=10,autocommit=False)

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--source-server",default="localhost")
    p.add_argument("--source-database",default="ReqSysMovimentoSourceDev")
    p.add_argument("--target-server",default="localhost")
    p.add_argument("--target-database",default="ReqSysMovimentoDev")
    p.add_argument("--source-tag",default="REQSYS_SOURCE_E2E")
    p.add_argument("--data-referencia",default="2099-12-29")
    a=p.parse_args()
    source_db=safe(a.source_database)
    target_db=safe(a.target_database)
    ref=date.fromisoformat(a.data_referencia)

    source=connect(a.source_server,source_db)
    target=connect(a.target_server,target_db)
    try:
        sc=source.cursor()
        tc=target.cursor()
        copied={}
        for table,(columns,width) in TABLES.items():
            sc.execute(f"SELECT {columns} FROM legacy_ssrs.{table} WHERE source_tag=? ORDER BY id",a.source_tag)
            rows=[tuple(row) for row in sc.fetchall()]
            tc.execute(f"DELETE FROM movimento_src.{table} WHERE source_tag=?",a.source_tag)
            if rows:
                placeholders=",".join("?" for _ in range(width))
                tc.executemany(f"INSERT INTO movimento_src.{table}({columns}) VALUES ({placeholders})",rows)
            copied[table]=len(rows)
        target.commit()

        views={
            "vw_prospeccao_movimento_fechamento_diario":copied["fechamento_diario"],
            "vw_prospeccao_movimento_pendencias_cadastro":copied["pendencias_cadastro"],
            "vw_prospeccao_movimento_pendencias_historicas":copied["pendencias_historicas"],
            "vw_prospeccao_movimento_pendencias_observacao":copied["pendencias_observacao"],
        }
        observed={}
        for view in views:
            tc.execute(f"SELECT COUNT(*) FROM dbo.{view} WHERE data_referencia=?",ref)
            observed[view]=int(tc.fetchone()[0])
        ok=observed==views
        print(json.dumps({"status":"validated" if ok else "failed","source_database":source_db,"target_database":target_db,"source_tag":a.source_tag,"copied":copied,"view_counts":observed,"expected_view_counts":views,"secrets_used":False,"corporate_source_validated":False},ensure_ascii=False))
        return 0 if ok else 3
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

if __name__=="__main__":
    raise SystemExit(main())
