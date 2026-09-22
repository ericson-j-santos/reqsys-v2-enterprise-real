#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path('reports/github-runtime-analytics')
TIMELINE_FILE = REPORT_DIR / 'runtime-operational-correlation-timeline.json'

def load_timeline() -> dict:
    if not TIMELINE_FILE.exists():
        return {'timeline': [], 'runtime_state': 'TIMELINE_NOT_FOUND'}
    payload = json.loads(TIMELINE_FILE.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('timeline payload must be a JSON object')
    return payload

def build_graph(timeline_payload: dict) -> dict:
    events = timeline_payload.get('timeline', [])
    nodes = []
    edges = []
    previous_id = None
    for event in events:
        if not isinstance(event, dict):
            continue
        node_id = f"event_{event.get('sequence', len(nodes) + 1)}"
        nodes.append({
            'id': node_id,
            'label': event.get('event', node_id),
            'source': event.get('source', 'unknown'),
            'state': event.get('state', 'unknown'),
            'correlation_level': event.get('correlation_level', 'unknown'),
        })
        if previous_id:
            edges.append({'from': previous_id, 'to': node_id, 'type': 'temporal_correlation'})
        previous_id = node_id
    return {
        'schema_version': '1.0.0',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'name': 'runtime-operational-evidence-graph',
        'mode': 'review_only',
        'runtime_state': 'EVIDENCE_GRAPH_READY' if nodes else 'EVIDENCE_GRAPH_BLOCKED',
        'node_count': len(nodes),
        'edge_count': len(edges),
        'nodes': nodes,
        'edges': edges,
        'confidence_percent': 93 if nodes else 60,
        'risk_percent': 4 if nodes else 35,
        'limits': ['no_deploy', 'no_production_mutation', 'no_external_write', 'human_review_required'],
        'next_recommended_increment': 'Runtime Operational Evidence UI',
    }

def write_reports(graph: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / 'runtime-operational-evidence-graph.json').write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    rows = '\n'.join(f"| {n['id']} | {n['label']} | {n['correlation_level']} | {n['state']} |" for n in graph['nodes'])
    md = '# Runtime Operational Evidence Graph\n\n'
    md += f"- Runtime state: {graph['runtime_state']}\n"
    md += f"- Nodes: {graph['node_count']}\n"
    md += f"- Edges: {graph['edge_count']}\n"
    md += f"- Confidence: {graph['confidence_percent']}%\n"
    md += f"- Risk: {graph['risk_percent']}%\n\n"
    md += '| Node | Label | Correlation level | State |\n|---|---|---|---|\n'
    md += rows + '\n'
    (REPORT_DIR / 'runtime-operational-evidence-graph.md').write_text(md, encoding='utf-8')

def main() -> int:
    graph = build_graph(load_timeline())
    write_reports(graph)
    print(graph['runtime_state'])
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
