#!/usr/bin/env python3
"""Score ReqSys Product Intelligence requirement quality.

This script intentionally uses only the Python standard library. It reads a
Product Intelligence event payload and generates JSON, Markdown and HTML reports
for CI artifacts and future dashboards.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVENT_PATH = ROOT / "examples" / "product-intelligence" / "product-intelligence-event.example.json"
REPORT_DIR = ROOT / "reports" / "product-intelligence"

WEIGHTS = {
    "bdd_coverage": 0.25,
    "ambiguity_score": 0.20,
    "traceability_score": 0.25,
    "risk_score": 0.15,
    "readiness_score": 0.15,
}


@dataclass(frozen=True)
class QualityScore:
    requirement_id: str
    event_type: str
    final_score: float
    maturity_level: str
    risk_band: str
    recommendation: str
    components: dict[str, float]


def load_event(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"event file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid event json: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("event root must be an object")
    return data


def clamp_score(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"quality.{field_name} must be numeric")
    if value < 0 or value > 100:
        raise ValueError(f"quality.{field_name} must be between 0 and 100")
    return float(value)


def maturity_level(score: float) -> str:
    if score >= 90:
        return "GOLD"
    if score >= 75:
        return "ADVANCED"
    if score >= 60:
        return "CONTROLLED"
    if score >= 40:
        return "PARTIAL"
    return "CRITICAL"


def risk_band(score: float) -> str:
    if score >= 80:
        return "LOW"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "HIGH"
    return "CRITICAL"


def recommendation(score: float, components: dict[str, float]) -> str:
    if score >= 90:
        return "Requirement is ready for governed implementation and test traceability."

    lowest = min(components, key=components.get)
    recommendations = {
        "bdd_coverage": "Increase BDD coverage before implementation.",
        "ambiguity_score": "Reduce ambiguity and clarify acceptance criteria.",
        "traceability_score": "Improve links to decisions, tests, PRs and risks.",
        "risk_score": "Reduce functional risk or add mitigation evidence.",
        "readiness_score": "Improve readiness before implementation planning.",
    }
    return recommendations.get(lowest, "Review requirement quality before implementation.")


def calculate_score(event: dict[str, Any]) -> QualityScore:
    requirement = event.get("requirement")
    quality = event.get("quality")
    if not isinstance(requirement, dict):
        raise ValueError("requirement must be an object")
    if not isinstance(quality, dict):
        raise ValueError("quality must be an object")

    components = {
        "bdd_coverage": clamp_score(quality.get("bdd_coverage"), "bdd_coverage"),
        "ambiguity_score": 100 - clamp_score(quality.get("ambiguity_score"), "ambiguity_score"),
        "traceability_score": clamp_score(quality.get("traceability_score"), "traceability_score"),
        "risk_score": 100 - clamp_score(quality.get("risk_score"), "risk_score"),
        "readiness_score": clamp_score(quality.get("readiness_score"), "readiness_score"),
    }
    final_score = sum(components[key] * WEIGHTS[key] for key in WEIGHTS)

    requirement_id = str(requirement.get("id") or "unknown")
    event_type = str(event.get("event_type") or "unknown")
    return QualityScore(
        requirement_id=requirement_id,
        event_type=event_type,
        final_score=round(final_score, 2),
        maturity_level=maturity_level(final_score),
        risk_band=risk_band(final_score),
        recommendation=recommendation(final_score, components),
        components={key: round(value, 2) for key, value in components.items()},
    )


def write_reports(score: QualityScore, report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "requirement_id": score.requirement_id,
        "event_type": score.event_type,
        "final_score": score.final_score,
        "maturity_level": score.maturity_level,
        "risk_band": score.risk_band,
        "recommendation": score.recommendation,
        "components": score.components,
        "weights": WEIGHTS,
    }
    (report_dir / "requirement-quality-score.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    markdown = f"""# Requirement Quality Score

| Field | Value |
|---|---|
| Requirement | {score.requirement_id} |
| Event type | {score.event_type} |
| Final score | {score.final_score} |
| Maturity level | {score.maturity_level} |
| Risk band | {score.risk_band} |

## Components

| Component | Score |
|---|---:|
| BDD coverage | {score.components['bdd_coverage']} |
| Ambiguity quality | {score.components['ambiguity_score']} |
| Traceability | {score.components['traceability_score']} |
| Risk quality | {score.components['risk_score']} |
| Readiness | {score.components['readiness_score']} |

## Recommendation

{score.recommendation}
"""
    (report_dir / "requirement-quality-score.md").write_text(markdown, encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Requirement Quality Score</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1200px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.label{{color:#94a3b8;font-size:14px}}
.metric{{font-size:34px;font-weight:bold;margin-top:8px;color:#22c55e}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{padding:12px;border-bottom:1px solid #1f2937;text-align:left}}
.section{{margin-top:28px}}
</style>
</head>
<body>
<div class="container">
<h1>Requirement Quality Score</h1>
<div class="grid">
<div class="card"><div class="label">Final Score</div><div class="metric">{score.final_score}</div></div>
<div class="card"><div class="label">Maturity</div><div class="metric">{score.maturity_level}</div></div>
<div class="card"><div class="label">Risk Band</div><div class="metric">{score.risk_band}</div></div>
</div>
<div class="section">
<h2>Components</h2>
<table>
<tr><th>Component</th><th>Score</th></tr>
<tr><td>BDD coverage</td><td>{score.components['bdd_coverage']}</td></tr>
<tr><td>Ambiguity quality</td><td>{score.components['ambiguity_score']}</td></tr>
<tr><td>Traceability</td><td>{score.components['traceability_score']}</td></tr>
<tr><td>Risk quality</td><td>{score.components['risk_score']}</td></tr>
<tr><td>Readiness</td><td>{score.components['readiness_score']}</td></tr>
</table>
</div>
<div class="section"><h2>Recommendation</h2><p>{score.recommendation}</p></div>
</div>
</body>
</html>
"""
    (report_dir / "requirement-quality-score.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    event_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EVENT_PATH
    report_dir = Path(argv[2]) if len(argv) > 2 else REPORT_DIR
    try:
        event = load_event(event_path)
        score = calculate_score(event)
        write_reports(score, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Requirement quality score: {score.final_score} ({score.maturity_level}, {score.risk_band})")
    print(f"Recommendation: {score.recommendation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
