#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db import Base, SessionLocal, engine
from app.models.auditoria import AuditoriaEvento
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit
from app.services import redmine_lifecycle_batch as batch
from app.services.github_redmine import _request_json, criar_issue_generica
from app.services.redmine_api import (
    _redmine_config,
    montar_campos_requisito_redmine,
    obter_issue_redmine,
)
from app.services.redmine_lifecycle_sync import (
    SYNC_STATE_TYPE,
    sincronizar_requisito_redmine,
)
from scripts.redmine_version_gate import evaluate_redmine_version

OUT = ROOT / "artifacts" / "redmine-e2e" / "evidence.json"


def save(data: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def state(db, rid: int, iid: int) -> dict:
    row = db.query(VinculoGit).filter(
        VinculoGit.requisito_id == rid,
        VinculoGit.provedor == "redmine",
        VinculoGit.tipo == SYNC_STATE_TYPE,
        VinculoGit.referencia == str(iid),
    ).first()
    return json.loads(row.titulo) if row and row.titulo else {}


def run() -> dict:
    version = os.environ["REDMINE_VERSION"]
    project_id = int(os.environ["REDMINE_PROJECT_ID"])
    reqsys_sha = os.environ["REQSYS_E2E_SHA"]
    decision = evaluate_redmine_version(version)
    assert decision.allowed, decision.reason

    base_url, key = _redmine_config()
    headers = {"X-Redmine-API-Key": key}
    current = _request_json("GET", f"{base_url}/users/current.json", headers=headers)["user"]
    user_id = int(current["id"])

    Base.metadata.create_all(bind=engine, tables=[
        Requisito.__table__, VinculoGit.__table__, AuditoriaEvento.__table__
    ])
    db = SessionLocal()
    correlation = f"redmine-e2e-{uuid4().hex}"
    suffix = uuid4().hex[:8].upper()
    try:
        req = Requisito(
            codigo=f"REQ-E2E-{suffix}", titulo="Inicial E2E", descricao="Inicial E2E",
            urgencia="media", area="Engenharia", sistema="ReqSys",
            solicitante="E2E automatizado", status="recebido", impacto_regulatorio=False,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        initial = montar_campos_requisito_redmine(req)
        created = criar_issue_generica(
            subject=initial["subject"], description=initial["description"], project_id=project_id
        )
        iid = int(created["issue_id"])
        db.add(VinculoGit(
            requisito_codigo=req.codigo, requisito_id=req.id, tipo="issue", provedor="redmine",
            repo="redmine", referencia=str(iid), url=f"{base_url}/issues/{iid}",
            titulo="ReqSys E2E", autor="e2e", ambiente="dev",
        ))
        db.commit()

        first_get = obter_issue_redmine(iid, incluir_journals=True)
        assert isinstance(first_get.get("journals"), list)

        req.titulo = f"Atualizado {suffix}"
        req.descricao = f"Descrição atualizada {suffix}"
        db.add(req)
        db.commit()
        db.refresh(req)
        out1 = sincronizar_requisito_redmine(
            db, requisito=req, correlation_id=f"{correlation}:put", actor="e2e"
        )
        assert out1["reqsys_to_redmine"]["applied"]
        expected = montar_campos_requisito_redmine(req)
        readback = obter_issue_redmine(iid, incluir_journals=True)
        assert readback["subject"] == expected["subject"]
        assert readback["description"] == expected["description"]

        rich = _request_json(
            "GET", f"{base_url}/issues/{iid}.json?include=journals,allowed_statuses", headers=headers
        )["issue"]
        current_status = int(rich["status"]["id"])
        allowed = rich.get("allowed_statuses") or []
        target = next(s for s in allowed if int(s["id"]) != current_status)
        note = f"ReqSys E2E journal {correlation}"
        _request_json("PUT", f"{base_url}/issues/{iid}.json", headers=headers, payload={"issue": {
            "status_id": int(target["id"]), "assigned_to_id": user_id, "done_ratio": 40, "notes": note
        }})
        remote = _request_json("GET", f"{base_url}/issues/{iid}.json?include=journals", headers=headers)["issue"]
        assert int(remote["status"]["id"]) == int(target["id"])
        assert int(remote["assigned_to"]["id"]) == user_id
        assert int(remote["done_ratio"]) == 40
        journal_ids = [int(j["id"]) for j in remote.get("journals", []) if j.get("notes") == note]
        assert journal_ids

        out2 = sincronizar_requisito_redmine(
            db, requisito=req, correlation_id=f"{correlation}:import", actor="e2e"
        )
        snapshot = state(db, req.id, iid)
        assert out2["redmine_to_reqsys"]["execution_changed"]
        assert max(journal_ids) in out2["redmine_to_reqsys"]["new_journal_ids"]
        assert int(snapshot["execution"]["status_id"]) == int(target["id"])
        assert int(snapshot["execution"]["assignee_id"]) == user_id
        assert int(snapshot["execution"]["done_ratio"]) == 40

        audits_before = db.query(AuditoriaEvento).filter(
            AuditoriaEvento.entidade_id == str(req.id)
        ).count()
        state_before = json.dumps(snapshot, sort_keys=True)
        replay = sincronizar_requisito_redmine(
            db, requisito=req, correlation_id=f"{correlation}:replay", actor="e2e"
        )
        audits_after = db.query(AuditoriaEvento).filter(
            AuditoriaEvento.entidade_id == str(req.id)
        ).count()
        assert replay["mutation_count"] == 0
        assert audits_after == audits_before
        assert json.dumps(state(db, req.id, iid), sort_keys=True) == state_before

        bad = Requisito(
            codigo=f"REQ-E2E-F-{suffix}", titulo="Falha E2E", descricao="Quarentena E2E",
            urgencia="media", area="Engenharia", sistema="ReqSys",
            solicitante="E2E automatizado", status="recebido", impacto_regulatorio=False,
        )
        db.add(bad)
        db.commit()
        db.refresh(bad)
        impossible = 999999999
        db.add(VinculoGit(
            requisito_codigo=bad.codigo, requisito_id=bad.id, tipo="issue", provedor="redmine",
            repo="redmine", referencia=str(impossible), url=f"{base_url}/issues/{impossible}",
            titulo="Falha E2E", autor="e2e", ambiente="dev",
        ))
        db.commit()

        t0 = datetime.now(timezone.utc)
        f1 = batch.reconciliar_requisito(
            db, requisito=bad, correlation_id=f"{correlation}:f1", actor="e2e",
            worker_id="e2e", max_tentativas=2, backoff_base_minutos=1,
            backoff_max_minutos=1, agora=t0,
        )
        f2 = batch.reconciliar_requisito(
            db, requisito=bad, correlation_id=f"{correlation}:f2", actor="e2e",
            worker_id="e2e", max_tentativas=2, backoff_base_minutos=1,
            backoff_max_minutos=1, agora=t0 + timedelta(minutes=2),
        )
        f3 = batch.reconciliar_requisito(
            db, requisito=bad, correlation_id=f"{correlation}:f3", actor="e2e",
            worker_id="e2e", max_tentativas=2, backoff_base_minutos=1,
            backoff_max_minutos=1, agora=t0 + timedelta(minutes=3),
        )
        assert f1["outcome"] == batch.OUTCOME_FAILED
        assert f2["outcome"] == batch.OUTCOME_QUARANTINED
        assert f3["outcome"] == batch.OUTCOME_SKIPPED_QUARANTINE
        controls = db.query(VinculoGit).filter(
            VinculoGit.requisito_id == bad.id, VinculoGit.tipo == batch.CONTROL_TYPE
        ).all()
        assert len(controls) == 1
        control = json.loads(controls[0].titulo)
        assert int(control["attempts"]) == 2 and control["quarantined"]
        assert not evaluate_redmine_version("6.1.3").allowed

        return {
            "status": "passed", "environment": "DEV-isolated-render", "reqsys_sha": reqsys_sha,
            "redmine": {"base_url": base_url, "version": version, "project_id": project_id,
                        "api_key_present": True, "authenticated_user_id": user_id},
            "correlation_id": correlation,
            "positive": {"requisito_id": req.id, "requisito_codigo": req.codigo,
                         "redmine_issue_id": iid, "get_journals": True,
                         "put_and_independent_readback": True, "remote_state_imported": True,
                         "journal_imported": True, "replay_mutation_count": replay["mutation_count"],
                         "replay_audit_delta": audits_after - audits_before},
            "negative": {"blocked_version_6_1_3": True, "first": f1["outcome"],
                         "second": f2["outcome"], "replay": f3["outcome"],
                         "attempts": control["attempts"], "quarantined": control["quarantined"],
                         "control_rows": len(controls)},
            "secret_values_in_evidence": False,
        }
    finally:
        db.close()


if __name__ == "__main__":
    try:
        evidence = run()
    except Exception as exc:
        save({
            "status": "failed",
            "error_type": type(exc).__name__,
            "error_ref": "redmine_e2e_runtime_failure",
            "secret_values_in_evidence": False,
        })
        print(f"REQSYS_REDMINE_E2E_FAILED type={type(exc).__name__}")
        raise SystemExit(1)
    save(evidence)
    print(
        "REQSYS_REDMINE_E2E_OK "
        f"sha={evidence['reqsys_sha']} project_id={evidence['redmine']['project_id']} "
        f"issue_id={evidence['positive']['redmine_issue_id']} "
        f"correlation_id={evidence['correlation_id']}"
    )
