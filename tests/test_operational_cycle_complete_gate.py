from __future__ import annotations

import json

from scripts.operational_cycle_complete_gate import (
    REQUIRED_FLAGS,
    evaluate_operational_cycle,
    load_json,
    write_report,
)


def _complete_payload() -> dict:
    return {
        "state": "green",
        "current_score": 99.27,
        "summary": {flag: True for flag in REQUIRED_FLAGS},
    }


def test_evaluate_operational_cycle_green_when_all_flags_ready() -> None:
    report = evaluate_operational_cycle(_complete_payload())

    assert report["status"] == "green"
    assert report["color"] == "green"
    assert report["operational_cycle_complete"] is True
    assert report["missing_flags"] == []
    assert report["next_action"] == "consolidar_ciclo_operacional"


def test_evaluate_operational_cycle_yellow_when_flag_missing() -> None:
    payload = _complete_payload()
    payload["summary"]["merge_readiness_history_enabled"] = False

    report = evaluate_operational_cycle(payload)

    assert report["status"] == "yellow"
    assert report["operational_cycle_complete"] is False
    assert report["missing_flags"] == ["merge_readiness_history_enabled"]
    assert report["next_action"] == "resolver_flags_pendentes_antes_de_consolidar"


def test_evaluate_operational_cycle_yellow_when_score_below_target() -> None:
    payload = _complete_payload()
    payload["current_score"] = 97.99

    report = evaluate_operational_cycle(payload)

    assert report["score_ready"] is False
    assert report["operational_cycle_complete"] is False


def test_load_json_returns_empty_for_missing_file(tmp_path) -> None:
    assert load_json(tmp_path / "missing.json") == {}


def test_write_report_creates_json(tmp_path) -> None:
    output = tmp_path / "report.json"
    report = evaluate_operational_cycle(_complete_payload())

    write_report(report, output)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["operational_cycle_complete"] is True
