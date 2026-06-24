#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_BY_AVAILABLE = {
    True: ("CONSOLIDATED", "green", "Evidence available"),
    False: ("MISSING", "red", "Evidence missing"),
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required final evidence index not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def classify_readiness(payload: dict[str, Any]) -> tuple[str, str]:
    coverage = float(payload.get("evidence_coverage_percent", 0.0))
    risk = float(payload.get("risk_percent", 100.0))
    if coverage >= 100.0 and risk <= 5.0:
        return "green", "Evidence navigation consolidated"
    if coverage >= 80.0 and risk <= 20.0:
        return "yellow", "Evidence navigation requires review"
    return "red", "Evidence navigation blocked"


def build_navigation_payload(index_payload: dict[str, Any]) -> dict[str, Any]:
    evidence = index_payload.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("final evidence index field 'evidence' must be a list")

    cards: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        available = bool(item.get("available"))
        state, color, description = STATUS_BY_AVAILABLE[available]
        artifact = str(item.get("artifact", "unknown-artifact"))
        path = str(item.get("path", ""))
        cards.append(
            {
                "artifact": artifact,
                "path": path,
                "available": available,
                "state": state,
                "status_color": color,
                "description": description,
                "anchor": artifact.replace(".", "-").replace("_", "-").lower(),
            }
        )

    readiness_color, readiness_label = classify_readiness(index_payload)
    available_count = sum(1 for card in cards if card["available"])
    missing_count = len(cards) - available_count

    return {
        "schema_version": "1.0.0",
        "name": "product-intelligence-evidence-navigation-ui",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "source": "product-intelligence-final-evidence-index.json",
        "readiness_state": index_payload.get("readiness_state", "UNKNOWN"),
        "readiness_color": readiness_color,
        "readiness_label": readiness_label,
        "evidence_coverage_percent": index_payload.get("evidence_coverage_percent", 0.0),
        "confidence_percent": index_payload.get("confidence_percent", 0),
        "risk_percent": index_payload.get("risk_percent", 100),
        "artifact_count": len(cards),
        "available_count": available_count,
        "missing_count": missing_count,
        "cards": cards,
        "human_review_required": True,
    }


def render_html(payload: dict[str, Any]) -> str:
    cards = payload["cards"]
    nav_items = "\n".join(
        f'<a href="#{html.escape(card["anchor"])}" class="nav-item {html.escape(card["status_color"])}">'
        f'{html.escape(card["artifact"])}'
        f'</a>'
        for card in cards
    )
    card_items = "\n".join(
        f'''<section id="{html.escape(card['anchor'])}" class="card {html.escape(card['status_color'])}">
  <div class="card-header">
    <strong>{html.escape(card['artifact'])}</strong>
    <span>{html.escape(card['state'])}</span>
  </div>
  <p>{html.escape(card['description'])}</p>
  <code>{html.escape(card['path'])}</code>
</section>'''
        for card in cards
    )
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Product Intelligence Evidence Navigation UI</title>
  <style>
    :root {{ --green:#137333; --yellow:#b06000; --red:#b3261e; --bg:#f8fafc; --card:#ffffff; --text:#172033; --muted:#667085; }}
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:24px; background:#0f172a; color:white; }}
    main {{ display:grid; grid-template-columns:280px 1fr; gap:20px; padding:20px; }}
    nav {{ position:sticky; top:20px; align-self:start; display:flex; flex-direction:column; gap:8px; }}
    .nav-item {{ text-decoration:none; color:var(--text); background:var(--card); border-left:6px solid var(--muted); padding:10px; border-radius:8px; font-size:13px; }}
    .summary {{ display:grid; grid-template-columns:repeat(5, minmax(120px, 1fr)); gap:12px; margin-bottom:20px; }}
    .metric, .card {{ background:var(--card); border-radius:12px; padding:16px; box-shadow:0 1px 4px rgba(15, 23, 42, .08); }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; }}
    .metric strong {{ display:block; font-size:22px; margin-top:6px; }}
    .card {{ border-left:8px solid var(--muted); margin-bottom:12px; }}
    .card-header {{ display:flex; justify-content:space-between; gap:16px; }}
    .green {{ border-left-color:var(--green); }}
    .yellow {{ border-left-color:var(--yellow); }}
    .red {{ border-left-color:var(--red); }}
    code {{ display:block; padding:10px; background:#eef2f7; border-radius:8px; overflow:auto; }}
    @media (max-width: 900px) {{ main {{ grid-template-columns:1fr; }} .summary {{ grid-template-columns:1fr 1fr; }} nav {{ position:static; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Product Intelligence Evidence Navigation UI</h1>
    <p>{html.escape(payload['readiness_label'])} · modo review_only · revisão humana obrigatória</p>
  </header>
  <main>
    <nav aria-label="Mapa navegável de evidências">
      {nav_items}
    </nav>
    <section>
      <div class="summary">
        <div class="metric"><span>Cobertura</span><strong>{payload['evidence_coverage_percent']}%</strong></div>
        <div class="metric"><span>Confiança</span><strong>{payload['confidence_percent']}%</strong></div>
        <div class="metric"><span>Risco</span><strong>{payload['risk_percent']}%</strong></div>
        <div class="metric"><span>Disponíveis</span><strong>{payload['available_count']}/{payload['artifact_count']}</strong></div>
        <div class="metric"><span>Status</span><strong>{html.escape(payload['readiness_color']).upper()}</strong></div>
      </div>
      {card_items}
    </section>
  </main>
</body>
</html>
'''


def render_markdown(payload: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{card['artifact']}` | {card['state']} | `{card['path']}` |"
        for card in payload["cards"]
    )
    return f'''# Product Intelligence Evidence Navigation UI

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_label']} |
| Status color | {payload['readiness_color']} |
| Evidence coverage | {payload['evidence_coverage_percent']}% |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |
| Available artifacts | {payload['available_count']} / {payload['artifact_count']} |

## Navigable evidence cards

| Artifact | State | Path |
|---|---|---|
{rows}

## Guardrail

This artifact is `review_only` and does not authorize production decisions without human governance review.
'''


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/product-intelligence")
    report_dir.mkdir(parents=True, exist_ok=True)
    final_index = load_json(report_dir / "product-intelligence-final-evidence-index.json")
    payload = build_navigation_payload(final_index)

    (report_dir / "product-intelligence-evidence-navigation-ui.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "product-intelligence-evidence-navigation-ui.html").write_text(
        render_html(payload),
        encoding="utf-8",
    )
    (report_dir / "product-intelligence-evidence-navigation-ui.md").write_text(
        render_markdown(payload),
        encoding="utf-8",
    )
    print(
        "Evidence navigation UI: "
        f"{payload['readiness_color']} "
        f"coverage={payload['evidence_coverage_percent']}% "
        f"available={payload['available_count']}/{payload['artifact_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
