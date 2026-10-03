#!/usr/bin/env python3
"""Validação E2E determinística do Operational Orchestrator.

Exercita fila -> gate -> executor -> Evidence Ledger e confirma o efeito por
leitura SQLite independente. Não usa rede, credenciais nem evidência residual.
Em CI, toda evidência é vinculada ao SHA exato da implementação em validação.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.operational_orchestrator import (  # noqa: E402
    OperationalActionIdentityConflictError,
    OperationalOrchestrator,
    OperationalStore,
)


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "environment": "development-e2e",
                "capabilities": {
                    "excel": {
                        "required": True,
                        "source": "env",
                        "references": ["REQSYS_E2E_EXCEL_ID"],
                        "description": "Fonte Excel controlada do E2E",
                    },
                    "sql_server": {
                        "required": True,
                        "source": "static",
                        "configured": True,
                        "description": "Destino SQL controlado do E2E",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _independent_rows(db_path: Path, correlation_id: str, sha: str) -> list[tuple[str, str, str]]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT status, sha, kind FROM evidence WHERE correlation_id = ? AND sha = ? ORDER BY observed_at",
            (correlation_id, sha),
        ).fetchall()


def _independent_action_payloads(db_path: Path, idempotency_key: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT payload_json FROM actions WHERE idempotency_key = ? ORDER BY created_at",
            (idempotency_key,),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def main() -> int:
    validation_sha = (os.getenv("REQSYS_VALIDATION_SHA") or "local-unbound").strip()
    if os.getenv("GITHUB_ACTIONS") == "true" and validation_sha == "local-unbound":
        raise RuntimeError("REQSYS_VALIDATION_SHA é obrigatório no CI para vincular a evidência ao SHA corrente.")

    with tempfile.TemporaryDirectory(prefix="reqsys-operational-orchestrator-") as tmp:
        base = Path(tmp)
        manifest = base / "readiness.yaml"
        db_path = base / "state.sqlite3"
        _write_manifest(manifest)

        positive = OperationalOrchestrator(
            store=OperationalStore(db_path),
            manifest_path=manifest,
            environ={"REQSYS_E2E_EXCEL_ID": "configured-only-in-memory"},
        )
        first = positive.run_cycle(sha=validation_sha, branch="e2e/positive")
        action = first["execution"]["action"]
        assert first["execution"]["executed"] is True
        assert first["execution"]["result"]["status"] == "ready"
        assert action["status"] == "succeeded"
        assert action["sha"] == validation_sha

        independent_positive = _independent_rows(
            db_path, action["correlation_id"], validation_sha
        )
        assert independent_positive == [("ready", validation_sha, "readiness")]

        repeated = positive.run_cycle(sha=validation_sha, branch="e2e/positive")
        assert repeated["action_created"] is False
        assert repeated["execution"]["reason"] == "already_succeeded"
        assert len(_independent_rows(db_path, action["correlation_id"], validation_sha)) == 1

        negative = OperationalOrchestrator(
            store=OperationalStore(db_path),
            manifest_path=manifest,
            environ={},
        )
        blocked = negative.run_cycle(sha=validation_sha, branch="e2e/negative")
        blocked_action = blocked["execution"]["action"]
        assert blocked["execution"]["result"]["status"] == "blocked"
        assert blocked["execution"]["result"]["missing_required"] == ["excel"]
        assert blocked_action["status"] == "blocked"
        assert blocked_action["sha"] == validation_sha
        independent_negative = _independent_rows(
            db_path, blocked_action["correlation_id"], validation_sha
        )
        assert independent_negative == [("blocked", validation_sha, "readiness")]

        idempotency_source = {
            "id": 4242,
            "name": "Operational Orchestrator CI",
            "status": "completed",
            "conclusion": "failure",
            "head_branch": "e2e/idempotency",
            "head_sha": validation_sha,
            "html_url": "https://github.com/example/actions/runs/4242",
        }
        idempotent_first = positive.ingest_workflow_run(idempotency_source)
        assert idempotent_first["created"] is True
        idempotent_replay = positive.ingest_workflow_run(idempotency_source)
        assert idempotent_replay["created"] is False
        assert (
            idempotent_replay["action"]["action_id"]
            == idempotent_first["action"]["action_id"]
        )

        divergent_source = {
            **idempotency_source,
            "name": "Operational Orchestrator CI adulterado",
            "html_url": "https://github.com/example/actions/runs/4242-divergent",
        }
        conflict_detected = False
        try:
            positive.ingest_workflow_run(divergent_source)
        except OperationalActionIdentityConflictError:
            conflict_detected = True
        assert conflict_detected is True

        idempotent_action = positive.store.get_action(
            idempotent_first["action"]["action_id"]
        )
        assert idempotent_action is not None
        independent_action_payloads = _independent_action_payloads(
            db_path, idempotent_action.idempotency_key
        )
        assert independent_action_payloads == [
            {
                "conclusion": "failure",
                "event": None,
                "html_url": "https://github.com/example/actions/runs/4242",
                "run_id": 4242,
                "workflow": "Operational Orchestrator CI",
            }
        ]

        # Teste do próprio teste: evidência do correlation_id correto não pode
        # satisfazer uma consulta vinculada a outro SHA.
        false_positive_probe = _independent_rows(
            db_path, action["correlation_id"], "sha-deliberadamente-incorreto"
        )
        assert false_positive_probe == []

        output = {
            "status": "passed",
            "implementation_sha": validation_sha,
            "implementation_sha_bound": validation_sha != "local-unbound",
            "positive": {
                "action_id": action["action_id"],
                "correlation_id": action["correlation_id"],
                "sha": validation_sha,
                "independent_evidence_count": len(independent_positive),
            },
            "negative": {
                "action_id": blocked_action["action_id"],
                "correlation_id": blocked_action["correlation_id"],
                "sha": validation_sha,
                "independent_evidence_count": len(independent_negative),
            },
            "idempotency": {
                "duplicate_action_created": repeated["action_created"],
                "evidence_count_after_repeat": len(
                    _independent_rows(db_path, action["correlation_id"], validation_sha)
                ),
                "workflow_replay_created": idempotent_replay["created"],
                "divergent_intent_conflict_detected": conflict_detected,
                "independent_action_count_after_conflict": len(independent_action_payloads),
                "original_workflow_preserved_after_conflict": (
                    independent_action_payloads[0]["workflow"]
                    == "Operational Orchestrator CI"
                ),
            },
            "false_positive_control": {
                "tampered_sha_evidence_count": len(false_positive_probe),
                "passed": len(false_positive_probe) == 0,
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
