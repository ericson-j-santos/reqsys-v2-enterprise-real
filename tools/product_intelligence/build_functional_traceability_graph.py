#!/usr/bin/env python3
"""Build a functional traceability graph from ReqSys Product Intelligence events.

The graph links requirements, PRs, tests, decisions and risks using only Python
standard library features so it can run in CI without changing runtime dependencies.
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


@dataclass(frozen=True)
class Node:
    id: str
    type: str
    label: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str


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


def as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def build_graph(event: dict[str, Any]) -> tuple[list[Node], list[Edge], dict[str, Any]]:
    requirement = event.get("requirement")
    traceability = event.get("traceability")
    quality = event.get("quality")
    governance = event.get("governance")

    if not isinstance(requirement, dict):
        raise ValueError("requirement must be an object")
    if not isinstance(traceability, dict):
        raise ValueError("traceability must be an object")
    if not isinstance(quality, dict):
        raise ValueError("quality must be an object")
    if not isinstance(governance, dict):
        raise ValueError("governance must be an object")

    requirement_id = str(requirement.get("id") or "unknown-requirement")
    requirement_title = str(requirement.get("title") or requirement_id)

    nodes: list[Node] = [Node(requirement_id, "requirement", requirement_title)]
    edges: list[Edge] = []

    relation_map = {
        "parent_ids": ("requirement", "parent"),
        "linked_prs": ("pull_request", "implemented_by"),
        "linked_tests": ("test", "validated_by"),
        "linked_decisions": ("decision", "decided_by"),
        "linked_risks": ("risk", "exposed_to"),
    }

    for field_name, (node_type, relation) in relation_map.items():
        for target_id in as_list(traceability.get(field_name)):
            nodes.append(Node(target_id, node_type, target_id))
            edges.append(Edge(requirement_id, target_id, relation))

    total_expected_groups = len(relation_map)
    populated_groups = sum(1 for field_name in relation_map if as_list(traceability.get(field_name)))
    edge_count = len(edges)
    node_count = len(nodes)
    coverage_score = round((populated_groups / total_expected_groups) * 100, 2)

    summary = {
        "requirement_id": requirement_id,
        "event_type": event.get("event_type", "unknown"),
        "node_count": node_count,
        "edge_count": edge_count,
        "traceability_groups": total_expected_groups,
        "populated_traceability_groups": populated_groups,
        "traceability_coverage_score": coverage_score,
        "correlation_id": governance.get("correlation_id"),
        "recommendation": recommendation(coverage_score, edge_count),
    }
    return nodes, edges, summary


def recommendation(coverage_score: float, edge_count: int) -> str:
    if coverage_score >= 80 and edge_count >= 4:
        return "Traceability is strong and ready for functional dashboarding."
    if coverage_score >= 40:
        return "Traceability is partial; add links to PRs, tests, decisions and risks before production governance."
    return "Traceability is weak; create functional links before implementation and validation."


def write_reports(nodes: list[Node], edges: list[Edge], summary: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "graph_type": "functional_traceability_graph",
        "schema_version": "1.0.0",
        "summary": summary,
        "nodes": [node.__dict__ for node in nodes],
        "edges": [edge.__dict__ for edge in edges],
    }
    (report_dir / "functional-traceability-graph.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    node_rows = "\n".join(f"| {node.id} | {node.type} | {node.label} |" for node in nodes)
    edge_rows = "\n".join(f"| {edge.source} | {edge.relation} | {edge.target} |" for edge in edges) or "| - | - | - |"
    markdown = f"""# Functional Traceability Graph

| Field | Value |
|---|---|
| Requirement | {summary['requirement_id']} |
| Event type | {summary['event_type']} |
| Nodes | {summary['node_count']} |
| Edges | {summary['edge_count']} |
| Traceability coverage | {summary['traceability_coverage_score']}% |
| Correlation ID | {summary.get('correlation_id')} |

## Recommendation

{summary['recommendation']}

## Nodes

| ID | Type | Label |
|---|---|---|
{node_rows}

## Edges

| Source | Relation | Target |
|---|---|---|
{edge_rows}
"""
    (report_dir / "functional-traceability-graph.md").write_text(markdown, encoding="utf-8")

    html_edges = "".join(
        f"<tr><td>{edge.source}</td><td>{edge.relation}</td><td>{edge.target}</td></tr>" for edge in edges
    ) or "<tr><td>-</td><td>-</td><td>-</td></tr>"
    html_nodes = "".join(
        f"<tr><td>{node.id}</td><td>{node.type}</td><td>{node.label}</td></tr>" for node in nodes
    )
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Functional Traceability Graph</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1300px;margin:0 auto}}
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
<h1>Functional Traceability Graph</h1>
<div class="grid">
<div class="card"><div class="label">Nodes</div><div class="metric">{summary['node_count']}</div></div>
<div class="card"><div class="label">Edges</div><div class="metric">{summary['edge_count']}</div></div>
<div class="card"><div class="label">Traceability Coverage</div><div class="metric">{summary['traceability_coverage_score']}%</div></div>
</div>
<div class="section"><h2>Recommendation</h2><p>{summary['recommendation']}</p></div>
<div class="section"><h2>Nodes</h2><table><tr><th>ID</th><th>Type</th><th>Label</th></tr>{html_nodes}</table></div>
<div class="section"><h2>Edges</h2><table><tr><th>Source</th><th>Relation</th><th>Target</th></tr>{html_edges}</table></div>
</div>
</body>
</html>
"""
    (report_dir / "functional-traceability-graph.html").write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    event_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EVENT_PATH
    report_dir = Path(argv[2]) if len(argv) > 2 else REPORT_DIR
    try:
        event = load_event(event_path)
        nodes, edges, summary = build_graph(event)
        write_reports(nodes, edges, summary, report_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "Functional traceability graph generated: "
        f"{summary['node_count']} nodes, {summary['edge_count']} edges, "
        f"coverage {summary['traceability_coverage_score']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
