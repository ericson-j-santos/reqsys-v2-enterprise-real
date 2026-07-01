from __future__ import annotations

import json
from pathlib import Path

from scripts.padrao_ouro_operational_consolidator import (
    REQUIRED_CYCLE,
    TIER1_ARTIFACTS,
    evaluate,
    main,
    tier1_status,
)


def _write_tier1(root: Path) -> None:
    for relative in TIER1_ARTIFACTS.values():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")


def _status(state: str = "green", *, new_front_allowed: bool = True) -> dict:
    allowed = ["gap_fix", "hotfix", "consolidate"]
    if new_front_allowed:
        allowed.append("new_front")
    return {
        "state": state,
        "decision": "continuar_proximo_incremento" if state == "green" else "bloquear_novas_frentes_ate_consolidar",
        "operational_cycle": list(REQUIRED_CYCLE),
        "increment_gate": {
            "new_front_allowed": new_front_allowed,
            "blockers": [] if new_front_allowed else ["state_yellow"],
            "allowed_increment_types": allowed,
        },
        "summary": {
            "open_prs": 1,
            "critical_gaps": 0,
            "red_workflows": 0,
            "pending_workflows": 0,
            "missing_critical_workflows": 0,
        },
        "recommended_actions": [],
    }


def test_tier1_status_reports_complete_when_all_artifacts_exist(tmp_path: Path) -> None:
    _write_tier1(tmp_path)

    report = tier1_status(tmp_path)

    assert report["complete"] is True
    assert report["missing"] == []


def test_evaluate_gold_when_green_and_tier1_complete(tmp_path: Path) -> None:
    _write_tier1(tmp_path)

    report = evaluate(_status("green", new_front_allowed=True), tier1_status(tmp_path))

    assert report["readiness"] == "gold"
    assert report["decision"] == "operacional_padrao_ouro_consolidado"
    assert report["next_increment_type"] == "new_front"
    assert report["hard_blockers"] == []


def test_evaluate_consolidating_when_yellow_allows_only_consolidation_lane(tmp_path: Path) -> None:
    _write_tier1(tmp_path)

    report = evaluate(_status("yellow", new_front_allowed=False), tier1_status(tmp_path))

    assert report["readiness"] == "consolidating"
    assert report["next_increment_type"] == "consolidate"
    assert report["hard_blockers"] == []
    assert any(action["action"] == "manter_modo_consolidacao" for action in report["recommended_actions"])


def test_evaluate_blocks_missing_tier1_artifact(tmp_path: Path) -> None:
    _write_tier1(tmp_path)
    (tmp_path / "docs/padrao-ouro/CONTRACT_CATALOG.md").unlink()

    report = evaluate(_status("green", new_front_allowed=True), tier1_status(tmp_path))

    assert report["readiness"] == "blocked"
    assert "tier1_artifacts_missing" in report["hard_blockers"]
    assert report["next_increment_type"] == "consolidate"


def test_cli_writes_report(tmp_path: Path) -> None:
    _write_tier1(tmp_path)
    status_path = tmp_path / "coordenador-status.json"
    output_path = tmp_path / "out.json"
    status_path.write_text(json.dumps(_status("green", new_front_allowed=True)), encoding="utf-8")

    exit_code = main(["--status-json", str(status_path), "--repo-root", str(tmp_path), "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["readiness"] == "gold"
