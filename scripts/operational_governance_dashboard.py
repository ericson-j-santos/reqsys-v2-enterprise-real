#!/usr/bin/env python3
"""Generate an executive HTML dashboard from Operational Governance Orchestrator JSON."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

STATUS_LABELS = {
    "green": "Verde",
    "yellow": "Atenção",
    "red": "Crítico",
    "pending": "Pendente",
    "unknown": "Indefinido",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def badge(status: str) -> str:
    label = STATUS_LABELS.get(status, status or "unknown")
    return f'<span class="badge badge-{esc(status)}">{esc(label)}</span>'


def metric_card(title: str, value: Any, hint: str = "") -> str:
    return f"""
    <section class="card metric-card">
      <span class="metric-title">{esc(title)}</span>
      <strong class="metric-value">{esc(value)}</strong>
      <span class="metric-hint">{esc(hint)}</span>
    </section>
    """


def run_rows(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return '<tr><td colspan="6" class="muted">Nenhum item encontrado.</td></tr>'
    rows = []
    for run in runs:
        rows.append(
            "<tr>"
            f"<td>{esc(run.get('name'))}</td>"
            f"<td>{badge(esc(run.get('health', 'unknown')))}</td>"
            f"<td>{esc(run.get('status'))}</td>"
            f"<td>{esc(run.get('conclusion'))}</td>"
            f"<td>{esc(run.get('event'))}</td>"
            f"<td><a href=\"{esc(run.get('url'))}\">abrir</a></td>"
            "</tr>"
        )
    return "\n".join(rows)


def pr_rows(prs: list[dict[str, Any]]) -> str:
    if not prs:
        return '<tr><td colspan="6" class="muted">Nenhum PR aberto.</td></tr>'
    rows = []
    for pr in prs:
        draft = "Sim" if pr.get("draft") else "Não"
        rows.append(
            "<tr>"
            f"<td>#{esc(pr.get('number'))}</td>"
            f"<td>{esc(pr.get('title'))}</td>"
            f"<td>{draft}</td>"
            f"<td>{esc(pr.get('base'))}</td>"
            f"<td>{esc(pr.get('head'))}</td>"
            f"<td><a href=\"{esc(pr.get('url'))}\">abrir</a></td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_html(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    state = report.get("state", "unknown")
    score = report.get("operational_score", 0)
    red_runs = report.get("red_runs", [])
    pending_runs = report.get("pending_runs", [])
    critical_runs = report.get("critical_runs", [])
    open_prs = report.get("open_prs", [])
    missing = report.get("missing_critical_workflows", [])

    missing_items = "".join(f"<li>{esc(item)}</li>" for item in missing) or "<li>Nenhum workflow crítico ausente.</li>"

    cards = "\n".join(
        [
            metric_card("Score operacional", f"{score}%", "baseado em workflows críticos verdes"),
            metric_card("Estado", STATUS_LABELS.get(state, state), report.get("decision", "")),
            metric_card("Runs críticos", summary.get("critical_runs", 0), "janela recente"),
            metric_card("Falhas críticas", summary.get("red", 0), "bloqueiam novos merges"),
            metric_card("Pendências", summary.get("pending", 0), "aguardar conclusão"),
            metric_card("PRs abertos", summary.get("open_prs", 0), "inclui drafts"),
        ]
    )

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Operational Governance Dashboard</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --panel-2: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --border: #334155;
      --green: #16a34a;
      --yellow: #ca8a04;
      --red: #dc2626;
      --blue: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 28px 24px; border-bottom: 1px solid var(--border); background: linear-gradient(135deg, #0f172a, #1e293b); }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin-top: 0; font-size: 20px; }}
    a {{ color: #93c5fd; }}
    main {{ padding: 24px; display: grid; gap: 20px; }}
    .meta {{ color: var(--muted); display: flex; flex-wrap: wrap; gap: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(6, minmax(150px, 1fr)); gap: 14px; }}
    .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.2); }}
    .metric-title {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric-value {{ display: block; margin: 8px 0; font-size: 26px; }}
    .metric-hint {{ color: var(--muted); font-size: 12px; }}
    .badge {{ display: inline-block; padding: 4px 9px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
    .badge-green {{ background: rgba(22,163,74,.18); color: #86efac; }}
    .badge-yellow, .badge-pending {{ background: rgba(202,138,4,.18); color: #fde68a; }}
    .badge-red {{ background: rgba(220,38,38,.18); color: #fecaca; }}
    .badge-unknown {{ background: rgba(37,99,235,.18); color: #bfdbfe; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); text-align: left; font-size: 13px; vertical-align: top; }}
    th {{ background: var(--panel-2); color: #cbd5e1; }}
    .muted {{ color: var(--muted); }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    ul {{ margin-bottom: 0; }}
    @media (max-width: 1100px) {{ .grid {{ grid-template-columns: repeat(3, 1fr); }} .two-col {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} main, header {{ padding: 16px; }} table {{ display: block; overflow-x: auto; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Operational Governance Dashboard {badge(state)}</h1>
    <div class="meta">
      <span>Repo: <strong>{esc(report.get('repository'))}</strong></span>
      <span>Branch: <strong>{esc(report.get('branch'))}</strong></span>
      <span>Modo: <strong>{esc(report.get('mode'))}</strong></span>
      <span>Atualizado: <strong>{esc(report.get('generated_at'))}</strong></span>
    </div>
  </header>
  <main>
    <section class="grid">{cards}</section>

    <section class="card">
      <h2>Workflows críticos</h2>
      <table>
        <thead><tr><th>Workflow</th><th>Saúde</th><th>Status</th><th>Conclusão</th><th>Evento</th><th>Link</th></tr></thead>
        <tbody>{run_rows(critical_runs)}</tbody>
      </table>
    </section>

    <section class="two-col">
      <section class="card">
        <h2>Falhas críticas</h2>
        <table>
          <thead><tr><th>Workflow</th><th>Saúde</th><th>Status</th><th>Conclusão</th><th>Evento</th><th>Link</th></tr></thead>
          <tbody>{run_rows(red_runs)}</tbody>
        </table>
      </section>
      <section class="card">
        <h2>Pendências</h2>
        <table>
          <thead><tr><th>Workflow</th><th>Saúde</th><th>Status</th><th>Conclusão</th><th>Evento</th><th>Link</th></tr></thead>
          <tbody>{run_rows(pending_runs)}</tbody>
        </table>
      </section>
    </section>

    <section class="card">
      <h2>PRs abertos</h2>
      <table>
        <thead><tr><th>PR</th><th>Título</th><th>Draft</th><th>Base</th><th>Head</th><th>Link</th></tr></thead>
        <tbody>{pr_rows(open_prs)}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>Workflows críticos ausentes na janela</h2>
      <ul>{missing_items}</ul>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate operational governance HTML dashboard.")
    parser.add_argument("--input", default="artifacts/operational-governance-orchestrator/operational-governance-orchestrator.json")
    parser.add_argument("--output", default="artifacts/operational-governance-orchestrator/dashboard.html")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    report = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(report), encoding="utf-8")
    print(f"Dashboard generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
