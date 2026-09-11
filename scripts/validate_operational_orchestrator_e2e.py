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

from app.services.operational_orchestrator import OperationalOrchestrator, OperationalStore  # noqa: E402


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "environment": "development-e2e",
                "capabilities": {
                    "source": {
                        "required": True,
                        "source": "env",
                        "references": ["REQSYS_E2E_SOURCE_ID"],
                        "description": "Fonte controlada do E2E",
                    },
                    "destination": {
                        "required": True,
                        "source": "static",
                        "configured": True,
                        "description": "Destino controlado do E2E",
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
            environ={"REQSYS_E2E_SOURCE_ID": "configured-only-in-memory"},
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
        assert blocked["execution"]["result"]["missing_required"] == ["source"]
        assert blocked_action["status"] == "blocked"
        assert blocked_action["sha"] == validation_sha
        independent_negative = _independent_rows(
            db_path, blocked_action["correlation_id"], validation_sha
        )
        assert independent_negative == [("blocked", validation_sha, "readiness")]

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
