#!/usr/bin/env python3
"""Consolida métricas da jornada real do usuário sem alterar contratos de runtime."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

KEY = "user_experience_journey_quality"
CARD_ID = "user-experience-journey-quality"


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def evaluate(evidence: dict[str, Any] | None) -> dict[str, Any]:
    source = evidence if isinstance(evidence, dict) else {}
    perceived_load_ms = max(0, int(source.get("perceived_load_ms", 0) or 0))
    actionable_error_rate = _clamp(float(source.get("actionable_error_rate", 0) or 0))
    empty_state_coverage = _clamp(float(source.get("empty_state_coverage", 0) or 0))
    accessibility_score = _clamp(float(source.get("accessibility_score", 0) or 0))
    feedback_coverage = _clamp(float(source.get("feedback_coverage", 0) or 0))

    if 0 < perceived_load_ms <= 1500:
        load_score = 100.0
    elif perceived_load_ms <= 2500 and perceived_load_ms > 0:
        load_score = 85.0
    elif perceived_load_ms <= 4000 and perceived_load_ms > 0:
        load_score = 65.0
    else:
        load_score = 0.0

    quality_score = round(
        load_score * 0.30
        + actionable_error_rate * 0.20
        + empty_state_coverage * 0.15
        + accessibility_score * 0.20
        + feedback_coverage * 0.15
    )
    evidence_complete = all(
        [perceived_load_ms > 0, actionable_error_rate > 0, empty_state_coverage > 0, accessibility_score > 0, feedback_coverage > 0]
    )
    status = "UX_JOURNEY_QUALITY_STABLE" if evidence_complete and quality_score >= 90 else "UX_JOURNEY_QUALITY_REVIEW"
    return {
        "id": CARD_ID,
        "title": "Qualidade da jornada do usuário",
        "status": status,
        "quality_score": quality_score,
        "perceived_load_ms": perceived_load_ms,
        "actionable_error_rate": actionable_error_rate,
        "empty_state_coverage": empty_state_coverage,
        "accessibility_score": accessibility_score,
        "feedback_coverage": feedback_coverage,
        "evidence_complete": evidence_complete,
        "human_review_eligible": status == "UX_JOURNEY_QUALITY_STABLE",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def consolidate(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any], indicator: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    state_out = deepcopy(state) if isinstance(state, dict) else {}
    brief_out = deepcopy(brief) if isinstance(brief, dict) else {}
    dashboard_out = deepcopy(dashboard) if isinstance(dashboard, dict) else {}
    state_out.setdefault("cards", {})[KEY] = indicator
    brief_out.setdefault("indicators", {})[KEY] = indicator
    cards = dashboard_out.get("cards", [])
    if not isinstance(cards, list):
        cards = []
    dashboard_out["cards"] = [item for item in cards if not (isinstance(item, dict) and item.get("id") == CARD_ID)] + [indicator]
    return state_out, brief_out, dashboard_out


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    indicator = evaluate(_read(args.evidence))
    state, brief, dashboard = consolidate(_read(args.state), _read(args.brief), _read(args.dashboard), indicator)
    _write(args.output_dir / "estado-unico.json", state)
    _write(args.output_dir / "executive-brief.json", brief)
    _write(args.output_dir / "ops-dashboard.json", dashboard)
    _write(args.output_dir / "user-experience-journey-quality.json", indicator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
