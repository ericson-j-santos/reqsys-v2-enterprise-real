#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required evidence graph not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def node_color(state: str, correlation_level: str) -> str:
    normalized_state = str(state).lower()
    if normalized_state in {"blocked", "failed", "error"}:
        return "red"
    if normalized_state in {"unknown", "pending", "review_required"}:
        return "yellow"
    if str(correlation_level).lower() in {"operational", "ci", "governance"}:
        return "green"
    return "yellow"


def classify(graph: dict[str, Any]) -> tuple[str, str]:
    runtime_state = str(graph.get("runtime_state", "UNKNOWN"))
    confidence = float(graph.get("confidence_percent", 0.0))
    risk = float(graph.get("risk_percent", 100.0))
    node_count = int(graph.get("node_count", 0))

    if runtime_state == "EVIDENCE_GRAPH_READY" and node_count > 0 and confidence >= 90 and risk <= 10:
        return "green", "Runtime evidence graph consolidated"
    if runtime_state in {"EVIDENCE_GRAPH_READY", "EVIDENCE_GRAPH_BLOCKED"} and node_count > 0:
        return "yellow", "Runtime evidence graph requires review"
    return "red", "Runtime evidence graph blocked"


def build_node_cards(graph: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", "unknown"))
        label = str(node.get("label", node_id))
        state = str(node.get("state", "unknown"))
        correlation_level = str(node.get("correlation_level", "unknown"))
        status_color = node_color(state, correlation_level)
        cards.append(
            {
                "id": node_id,
                "label": label,
                "source": str(node.get("source", "unknown")),
                "state": state,
                "correlation_level": correlation_level,
                "status_color": status_color,
                "anchor": node_id.replace("_", "-").lower(),
            }
        )
    return cards


def build_edge_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        rows.append(
            {
                "from": str(edge.get("from", "unknown")),
                "to": str(edge.get("to", "unknown")),
                "type": str(edge.get("type", "unknown")),
            }
        )
    return rows


def build_payload(graph: dict[str, Any]) -> dict[str, Any]:
    cards = build_node_cards(graph)
    edges = build_edge_rows(graph)
    readiness_color, readiness_label = classify(graph)
    green_count = sum(1 for card in cards if card["status_color"] == "green")

    return {
        "schema_version": "1.0.0",
        "name": "runtime-operational-evidence-ui",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only",
        "source": "runtime-operational-evidence-graph.json",
        "runtime_state": graph.get("runtime_state", "UNKNOWN"),
        "readiness_color": readiness_color,
        "readiness_label": readiness_label,
        "confidence_percent": graph.get("confidence_percent", 0),
        "risk_percent": graph.get("risk_percent", 100),
        "node_count": len(cards),
        "edge_count": len(edges),
        "consolidated_nodes": green_count,
        "cards": cards,
        "edges": edges,
        "human_review_required": True,
        "next_recommended_increment": "Runtime Evidence Graph Dashboard Integration",
    }


def render_html(payload: dict[str, Any]) -> str:
    nav = "\n".join(
        f'<a href="#{html.escape(card["anchor"])}" class="nav-item {html.escape(card["status_color"])}">{html.escape(card["label"])}</a>'
        for card in payload["cards"]
    )
    cards = "\n".join(
        f'''<section id="{html.escape(card['anchor'])}" class="card {html.escape(card['status_color'])}">
  <div class="card-header"><strong>{html.escape(card['label'])}</strong><span>{html.escape(card['state'])}</span></div>
  <div class="meta"><span>ID: <code>{html.escape(card['id'])}</code></span><span>Source: <code>{html.escape(card['source'])}</code></span><span>Correlation: <code>{html.escape(card['correlation_level'])}</code></span></div>
</section>'''
        for card in payload["cards"]
    )
    edge_rows = "\n".join(
        f"<tr><td><code>{html.escape(edge['from'])}</code></td><td><code>{html.escape(edge['to'])}</code></td><td>{html.escape(edge['type'])}</td></tr>"
        for edge in payload["edges"]
    )
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Runtime Operational Evidence UI</title>
<style>
:root {{ --green:#137333; --yellow:#b06000; --red:#b3261e; --bg:#f8fafc; --card:#fff; --text:#172033; --muted:#667085; }}
body {{ margin:0; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--text); }}
header {{ padding:24px; background:#0f172a; color:white; }}
main {{ display:grid; grid-template-columns:280px 1fr; gap:20px; padding:20px; }}
nav {{ position:sticky; top:20px; align-self:start; display:flex; flex-direction:column; gap:8px; }}
.nav-item {{ text-decoration:none; color:var(--text); background:var(--card); border-left:6px solid var(--muted); padding:10px; border-radius:8px; font-size:13px; }}
.summary {{ display:grid; grid-template-columns:repeat(5, minmax(120px, 1fr)); gap:12px; margin-bottom:20px; }}
.metric, .card, .edges {{ background:var(--card); border-radius:12px; padding:16px; box-shadow:0 1px 4px rgba(15,23,42,.08); }}
.metric span {{ display:block; color:var(--muted); font-size:12px; }}
.metric strong {{ display:block; font-size:22px; margin-top:6px; }}
.card {{ border-left:8px solid var(--muted); margin-bottom:12px; }}
.card-header {{ display:flex; justify-content:space-between; gap:16px; margin-bottom:10px; }}
.meta {{ display:flex; flex-wrap:wrap; gap:12px; font-size:13px; color:var(--muted); }}
.green {{ border-left-color:var(--green); }} .yellow {{ border-left-color:var(--yellow); }} .red {{ border-left-color:var(--red); }}
table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
th, td {{ padding:10px; border-bottom:1px solid #e5e7eb; text-align:left; font-size:13px; }}
th {{ background:#eef2f7; }}
code {{ background:#eef2f7; padding:2px 6px; border-radius:6px; }}
@media (max-width:900px) {{ main {{ grid-template-columns:1fr; }} .summary {{ grid-template-columns:1fr 1fr; }} nav {{ position:static; }} }}
</style>
</head>
<body>
<header><h1>Runtime Operational Evidence UI</h1><p>{html.escape(payload['readiness_label'])} · review_only · revisão humana obrigatória</p></header>
<main>
<nav aria-label="Mapa navegável do grafo de evidências">{nav}</nav>
<section>
<div class="summary">
<div class="metric"><span>Nodes</span><strong>{payload['node_count']}</strong></div>
<div class="metric"><span>Edges</span><strong>{payload['edge_count']}</strong></div>
<div class="metric"><span>Confiança</span><strong>{payload['confidence_percent']}%</strong></div>
<div class="metric"><span>Risco</span><strong>{payload['risk_percent']}%</strong></div>
<div class="metric"><span>Status</span><strong>{html.escape(payload['readiness_color']).upper()}</strong></div>
</div>
{cards}
<div class="edges">
<h2>Correlações temporais</h2>
<table><thead><tr><th>From</th><th>To</th><th>Type</th></tr></thead><tbody>{edge_rows}</tbody></table>
</div>
</section>
</main>
</body>
</html>
'''


def render_markdown(payload: dict[str, Any]) -> str:
    node_rows = "\n".join(
        f"| `{card['id']}` | {card['label']} | {card['correlation_level']} | {card['state']} | {card['status_color']} |"
        for card in payload["cards"]
    )
    edge_rows = "\n".join(
        f"| `{edge['from']}` | `{edge['to']}` | {edge['type']} |"
        for edge in payload["edges"]
    )
    return f'''# Runtime Operational Evidence UI

| Field | Value |
|---|---:|
| Readiness | {payload['readiness_label']} |
| Status color | {payload['readiness_color']} |
| Runtime state | {payload['runtime_state']} |
| Nodes | {payload['node_count']} |
| Edges | {payload['edge_count']} |
| Confidence | {payload['confidence_percent']}% |
| Risk | {payload['risk_percent']}% |

## Navigable graph nodes

| Node | Label | Correlation | State | Color |
|---|---|---|---|---|
{node_rows}

## Temporal correlations

| From | To | Type |
|---|---|---|
{edge_rows}

## Guardrail

This artifact is `review_only` and does not authorize production decisions without human governance review.
'''


def write_reports(report_dir: Path, payload: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "runtime-operational-evidence-ui.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "runtime-operational-evidence-ui.html").write_text(
        render_html(payload),
        encoding="utf-8",
    )
    (report_dir / "runtime-operational-evidence-ui.md").write_text(
        render_markdown(payload),
        encoding="utf-8",
    )


def main() -> int:
    report_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/github-runtime-analytics")
    graph = load_json(report_dir / "runtime-operational-evidence-graph.json")
    payload = build_payload(graph)
    write_reports(report_dir, payload)
    print(
        f"Runtime evidence UI: {payload['readiness_color']} "
        f"nodes={payload['node_count']} edges={payload['edge_count']} "
        f"confidence={payload['confidence_percent']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
