#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def esc(value) -> str:
    return str(value if value is not None else '-')


def build_dashboard(hub: dict, risk: dict, drift: dict, governance: dict, history: list) -> str:
    hub_score = hub.get('hub_score', {}).get('score', 0)
    hub_status = hub.get('hub_score', {}).get('status', 'SEM_DADOS')
    risk_score = risk.get('risk_score', 0)
    risk_level = risk.get('risk_level', 'DESCONHECIDO')
    drift_level = drift.get('drift_level', 'DESCONHECIDO')
    forecast = drift.get('forecast', 'ESTAVEL')
    governance_status = governance.get('gate_status', 'UNKNOWN')
    stability = drift.get('stability_index', 0)

    history_rows = []
    for item in history[-10:]:
        metrics = item.get('metrics', {})
        history_rows.append(
            f"<tr><td>{esc(item.get('snapshot_at_utc'))}</td><td>{esc(item.get('hub_score'))}</td><td>{esc(metrics.get('overall_failure_rate_percent'))}%</td></tr>"
        )

    return f"""<!doctype html>
<html lang='pt-BR'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>ReqSys Operational Executive Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e5e7eb;font-family:Arial,Helvetica,sans-serif}}
main{{max-width:1400px;margin:auto;padding:24px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.card{{background:#111827;border:1px solid #374151;border-radius:18px;padding:20px}}
.value{{font-size:32px;font-weight:800;margin-top:8px}}
.label{{color:#9ca3af;font-size:13px}}
.ok{{color:#22c55e}}.warn{{color:#f59e0b}}.bad{{color:#ef4444}}
.table{{margin-top:16px;width:100%;border-collapse:collapse}}
.table td,.table th{{padding:12px;border-bottom:1px solid #374151;text-align:left}}
.table th{{color:#9ca3af}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;background:#2563eb;color:white;font-size:12px}}
@media(max-width:1000px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<main>
<h1>ReqSys Operational Executive Dashboard</h1>
<p>Visão executiva consolidada operacional, histórica e governada.</p>

<section class='grid'>
<div class='card'><div class='label'>Operational Score</div><div class='value'>{hub_score}%</div><div class='badge'>{hub_status}</div></div>
<div class='card'><div class='label'>Risk Level</div><div class='value'>{risk_level}</div><div class='badge'>Risk {risk_score}</div></div>
<div class='card'><div class='label'>Drift Level</div><div class='value'>{drift_level}</div><div class='badge'>{forecast}</div></div>
<div class='card'><div class='label'>Governance Gate</div><div class='value'>{governance_status}</div><div class='badge'>Stability {stability}</div></div>
</section>

<section class='card' style='margin-top:16px'>
<h2>Operational Timeline</h2>
<table class='table'>
<thead><tr><th>Snapshot UTC</th><th>Score</th><th>Failure Rate</th></tr></thead>
<tbody>
{''.join(history_rows)}
</tbody>
</table>
</section>

<section class='grid' style='margin-top:16px'>
<div class='card'>
<h3>Risk + Drift + Governance Fusion</h3>
<ul>
<li>Risk Score: {risk_score}</li>
<li>Drift Level: {drift_level}</li>
<li>Forecast: {forecast}</li>
<li>Governance Gate: {governance_status}</li>
</ul>
</div>
<div class='card'>
<h3>Operational Recommendations</h3>
<ul>
<li>Monitorar workflows críticos continuamente.</li>
<li>Priorizar redução de MTTR operacional.</li>
<li>Evitar degradação silenciosa prolongada.</li>
<li>Manter governança baseada em evidência.</li>
</ul>
</div>
</section>

<div class='card' style='margin-top:16px'>
Gerado em UTC: {datetime.now(timezone.utc).isoformat()}<br>
Zero-CDN · Artifact auditável · Sem automação destrutiva.
</div>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description='ReqSys Operational Executive Dashboard')
    parser.add_argument('--hub', type=Path, default=Path('artifacts/operational-intelligence-hub/operational-intelligence-hub.json'))
    parser.add_argument('--risk', type=Path, default=Path('artifacts/operational-risk-engine/operational-risk-engine.json'))
    parser.add_argument('--drift', type=Path, default=Path('artifacts/operational-drift-analyzer/operational-drift-analyzer.json'))
    parser.add_argument('--governance', type=Path, default=Path('artifacts/operational-governance-gate/operational-governance-gate.json'))
    parser.add_argument('--history', type=Path, default=Path('artifacts/operational-history/operational-history.json'))
    parser.add_argument('--out-dir', type=Path, default=Path('artifacts/operational-executive-dashboard'))
    args = parser.parse_args()

    hub = load_json(args.hub, {})
    risk = load_json(args.risk, {})
    drift = load_json(args.drift, {})
    governance = load_json(args.governance, {})
    history = load_json(args.history, [])

    args.out_dir.mkdir(parents=True, exist_ok=True)

    html = build_dashboard(hub, risk, drift, governance, history if isinstance(history, list) else [])

    (args.out_dir / 'index.html').write_text(html, encoding='utf-8')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
