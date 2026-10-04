from __future__ import annotations

import json
from pathlib import Path

from scripts.build_merge_readiness_history import (
    build_metrics,
    build_payload,
    ingest_gate_report,
    merge_history,
    snapshot_from_gate,
)


def test_snapshot_from_gate_mapeia_campos():
    gate = {
        "status": "blocked",
        "base_ref": "main",
        "ahead_by": 2,
        "behind_by": 1,
        "changed_files": 12,
        "workflow_files": 1,
        "domains": ["backend", "docs"],
        "blocking_issues": ["Branch está 1 commit(s) atrás de main; rebase/update obrigatório antes do merge."],
        "warnings": [],
    }

    snapshot = snapshot_from_gate(gate, run_id="123456", correlation_id="corr-merge-001")

    assert snapshot["status"] == "blocked"
    assert snapshot["behind_by"] == 1
    assert snapshot["blocking_codes"] == ["branch_behind"]
    assert "/actions/runs/123456" in snapshot["workflow_run_url"]


def test_merge_history_deduplica_run_id():
    existing = [{"run_id": "1", "status": "ready", "changed_files": 3}]
    updated = snapshot_from_gate({"status": "blocked", "changed_files": 8, "blocking_issues": []}, run_id="1")

    merged = merge_history(existing, updated)

    assert len(merged) == 1
    assert merged[0]["status"] == "blocked"


def test_build_metrics_calcula_taxa_de_bloqueio():
    history = [
        {"status": "ready", "changed_files": 4, "workflow_files": 0, "behind_by": 0, "domains": ["backend"]},
        {"status": "blocked", "changed_files": 10, "workflow_files": 2, "behind_by": 2, "domains": ["backend", "docs"]},
    ]

    metrics = build_metrics(history)

    assert metrics["samples"] == 2
    assert metrics["blocked_rate"] == 0.5
    assert metrics["avg_changed_files"] == 7.0
    assert metrics["top_domains"][0]["domain"] == "backend"


def test_ingest_gate_report_persiste_historico(tmp_path: Path):
    report = tmp_path / "merge-readiness.json"
    output = tmp_path / "merge-readiness-history.json"
    report.write_text(
        json.dumps(
            {
                "status": "ready",
                "base_ref": "main",
                "ahead_by": 1,
                "behind_by": 0,
                "changed_files": 5,
                "workflow_files": 0,
                "domains": ["tests"],
                "blocking_issues": [],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    payload = ingest_gate_report(str(report), str(output), run_id="run-merge-1", correlation_id="corr-1")

    assert payload["summary"]["samples"] == 1
    assert payload["latest_snapshot"]["run_id"] == "run-merge-1"
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["history"][0]["correlation_id"] == "corr-1"


def test_build_payload_estado_amarelo_com_bloqueios_parciais():
    payload = build_payload(
        [
            {"status": "ready", "changed_files": 2, "workflow_files": 0, "behind_by": 0, "domains": [], "blocking_count": 0},
            {"status": "ready", "changed_files": 3, "workflow_files": 0, "behind_by": 0, "domains": [], "blocking_count": 0},
            {"status": "blocked", "changed_files": 4, "workflow_files": 1, "behind_by": 1, "domains": ["docs"], "blocking_count": 1},
        ]
    )

    assert payload["state"] == "yellow"
    assert round(payload["summary"]["blocked_rate"], 2) == 0.33
    assert payload["summary"]["merge_readiness_stabilized"] is False


def test_build_payload_merge_readiness_estabilizado():
    payload = build_payload(
        [
            {"status": "ready", "changed_files": 4, "workflow_files": 0, "behind_by": 0, "domains": ["backend"], "blocking_count": 0},
            {"status": "ready", "changed_files": 5, "workflow_files": 0, "behind_by": 0, "domains": ["tests"], "blocking_count": 0},
            {"status": "ready", "changed_files": 6, "workflow_files": 0, "behind_by": 0, "domains": ["docs"], "blocking_count": 0},
        ]
    )

    assert payload["state"] == "green"
    assert payload["summary"]["merge_readiness_stabilized"] is True
