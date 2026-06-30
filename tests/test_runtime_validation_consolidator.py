from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime_validation_consolidator import (
    DEFAULT_INPUTS,
    build_domains,
    build_snapshot,
    compute_gold_standard_operational_risk,
    compute_production_ready,
    compute_validation_score,
    evaluate_public_smoke,
    write_report,
)


def test_public_smoke_green_when_all_endpoints_ok() -> None:
    payload = {"failed": 0, "total": 4, "ok": 4, "success_percentual": 100.0}
    result = evaluate_public_smoke(payload)
    assert result["state"] == "green"
    assert result["score"] == 100


def test_public_smoke_red_when_failures() -> None:
    payload = {"failed": 2, "total": 4, "success_percentual": 50.0}
    result = evaluate_public_smoke(payload)
    assert result["state"] == "red"


def test_build_snapshot_with_local_audit_artifacts(tmp_path: Path) -> None:
    audit = tmp_path / "audit" / "runtime"
    audit.mkdir(parents=True)
    (audit / "public-runtime-validation.json").write_text(
        json.dumps(
            {
                "failed": 0,
                "total": 4,
                "ok": 4,
                "success_percentual": 100.0,
                "readiness": {
                    "readiness_percent": 100.0,
                    "operational_status": "healthy",
                    "blocking_issues": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (audit / "ops-readiness-report.json").write_text(
        json.dumps(
            {
                "readiness_percent": 100.0,
                "operational_status": "healthy",
                "blocking_issues": [],
            }
        ),
        encoding="utf-8",
    )
    trilha = tmp_path / "audit" / "trilha-a"
    trilha.mkdir(parents=True)
    (trilha / "trilha-a-runtime-publico-report.json").write_text(
        json.dumps({"status": "passed", "summary": {"tracks_ok": 3, "tracks_total": 3, "validator_ok": True}}),
        encoding="utf-8",
    )
    health_dir = tmp_path / "artifacts" / "runtime-health-validator"
    health_dir.mkdir(parents=True)
    (health_dir / "runtime-health-validator.json").write_text(
        json.dumps({"state": "green", "runtime_score": 88, "executive_status": "ok"}),
        encoding="utf-8",
    )
    center_dir = tmp_path / "artifacts" / "runtime-health-center"
    center_dir.mkdir(parents=True)
    (center_dir / "runtime-health-report.json").write_text(
        json.dumps(
            {
                "maturity_percent": 90,
                "operational_risk": "low",
                "gold_standard_depth": {"overall_score": 92},
            }
        ),
        encoding="utf-8",
    )

    snapshot = build_snapshot("owner/repo", "main", root=tmp_path)
    assert snapshot["validation_score"] >= 75
    assert snapshot["public_runtime_ready"] is True
    assert snapshot["gold_standard_operational_risk"]["overall_score"] >= 65
    assert "public_smoke" in snapshot["domains"]


def test_gold_standard_reaches_target_when_all_domains_green() -> None:
    domains = {
        "public_smoke": {"state": "green", "score": 100},
        "public_readiness": {"state": "green", "score": 100},
        "post_merge": {"state": "green", "score": 100},
        "health_validator": {"state": "green", "score": 100},
        "trilha_a": {"state": "green", "score": 100},
        "evidence_gate": {"state": "green", "score": 100},
        "health_center": {"state": "green", "score": 100},
    }
    sources_meta = {name: {"available": True} for name in list(DEFAULT_INPUTS.keys())}
    gold = compute_gold_standard_operational_risk(domains, sources_meta, root=Path("."))
    assert gold["overall_score"] >= 95
    assert gold["status"] == "gold"
    assert compute_validation_score(domains) == 100


def test_write_report_creates_three_files(tmp_path: Path) -> None:
    snapshot = build_snapshot("owner/repo", "main", root=tmp_path)
    out = tmp_path / "out"
    write_report(snapshot, out, "owner/repo", "main")
    assert (out / "runtime-validation-snapshot.json").exists()
    assert (out / "summary.md").exists()
    assert (out / "executive-brief.json").exists()
    brief = json.loads((out / "executive-brief.json").read_text(encoding="utf-8"))
    assert "risco_operacional_percent" in brief["indicadores_executivos"]
    assert "padrao_ouro_operacional_risco_percent" in brief["indicadores_executivos"]
    assert (out / "operational-acceptance-record.json").exists()


def test_domains_handle_missing_sources() -> None:
    domains = build_domains({})
    assert domains["public_smoke"]["state"] == "red"
    assert domains["post_merge"]["available"] is False


def test_production_ready_when_gold_and_runtime_green() -> None:
    gold = {"status": "gold", "overall_score": 100}
    assert compute_production_ready(
        gold=gold,
        public_runtime_ready=True,
        validation_score=91,
        operational_risk_percent=9,
        blockers=[],
    )


def test_production_ready_false_when_critical_blocker() -> None:
    gold = {"status": "gold", "overall_score": 100}
    assert not compute_production_ready(
        gold=gold,
        public_runtime_ready=True,
        validation_score=91,
        operational_risk_percent=9,
        blockers=["public_runtime_not_evidenced"],
    )


def test_production_ready_ignores_post_merge_incomplete() -> None:
    gold = {"status": "gold", "overall_score": 100}
    assert compute_production_ready(
        gold=gold,
        public_runtime_ready=True,
        validation_score=91,
        operational_risk_percent=9,
        blockers=["post_merge_validation_incomplete"],
    )


def test_snapshot_marks_production_ready_on_main_tree() -> None:
    snapshot = build_snapshot("owner/repo", "main", root=Path("/workspace"))
    assert snapshot["gold_standard_operational_risk"]["overall_score"] == 100
    assert snapshot["production_ready"] is True
    assert snapshot["operational_risk_percent"] <= 15
