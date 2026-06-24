#!/usr/bin/env python3
"""Generate a zero-CDN HTML Operational Center from Operational Intelligence Hub JSON."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "fallback",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "hub_score": {"status": "SEM_DADOS", "score": 0, "confidence": "baixa", "components": []},
            "available_layers": [],
            "missing_layers": ["operational_health", "operational_ci_intelligence", "failure_pattern_engine", "actions_deep_diagnostic"],
            "source_reports": {},
            "recommendations": ["Executar Operational Intelligence Hub para gerar dados consolidados."],
            "blocked_actions": ["auto_merge", "auto_fix_in_production", "unrestricted_rerun"],
            "limits": ["HTML gerado sem arquivo JSON de entrada; dados demonstrativos/fallback."],
        }
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Entrada invalida: esperado objeto JSON.")
    return data


def status_class(status: Any) -> str:
    normalized = str(status or "").upper()
    if normalized in {"VERDE", "PASSED", "SUCCESS"}:
        return "ok"
    if normalized in {"AMARELO", "WARNING", "PENDING"}:
        return "warn"
    if normalized in {"VERMELHO", "FAILED", "FAILURE", "ERROR"}:
        return "bad"
    return "neutral"


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else "-"))


def render_list(items: list[Any]) -> str:
    if not items:
        return "<li>Nenhum item informado.</li>"
    return "\n".join(f"<li>{esc(item)}</li>" for item in items)


def render_layers(source_reports: dict[str, Any]) -> str:
    if not source_reports:
        return "<tr><td colspan='5'>Sem camadas informadas.</td></tr>"
    rows = []
    for name, summary in source_reports.items():
        status = summary.get("status") or "-"
        rows.append(
            "<tr>"
            f"<td><strong>{esc(name)}</strong></td>"
            f"<td>{esc(summary.get('available'))}</td>"
            f"<td><span class='badge {status_class(status)}'>{esc(status)}</span></td>"
            f"<td>{esc(summary.get('score'))}</td>"
            f"<td><code>{esc(summary.get('path'))}</code></td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_components(components: list[dict[str, Any]]) -> str:
    if not components:
        return "<tr><td colspan='3'>Sem componentes de score.</td></tr>"
    return "\n".join(
        "<tr>"
        f"<td>{esc(component.get('name'))}</td>"
        f"<td>{esc(component.get('score'))}</td>"
        f"<td>{esc(component.get('weight'))}</td>"
        "</tr>"
        for component in components
    )


def render_html(report: dict[str, Any]) -> str:
    hub = report.get("hub_score", {})
    status = hub.get("status", "SEM_DADOS")
    score = hub.get("score", 0)
    confidence = hub.get("confidence", "baixa")
    generated_at = report.get("generated_at_utc") or datetime.now(timezone.utc).isoformat()
    available_layers = report.get("available_layers", [])
    missing_layers = report.get("missing_layers", [])
    source_reports = report.get("source_reports", {})
    recommendations = report.get("recommendations", [])
    blocked_actions = report.get("blocked_actions", [])
    limits = report.get("limits", [])
    raw_json = json.dumps(report, ensure_ascii=False, indent=2)

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ReqSys Operational Center</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --panel2: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --line: #374151;
      --ok: #16a34a;
      --warn: #f59e0b;
      --bad: #dc2626;
      --neutral: #64748b;
      --blue: #2563eb;
      --cyan: #0891b2;
      --white: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ padding: 28px 24px; border-bottom: 1px solid var(--line); background: linear-gradient(135deg, #111827, #0f172a 70%); }}
    h1 {{ margin: 0 0 8px; font-size: clamp(24px, 4vw, 40px); }}
    h2 {{ margin: 0 0 16px; font-size: 20px; }}
    h3 {{ margin: 0 0 12px; font-size: 16px; color: var(--white); }}
    p {{ color: var(--muted); line-height: 1.55; }}
    main {{ padding: 24px; max-width: 1280px; margin: 0 auto; }}
    .grid {{ display: grid; gap: 16px; }}
    .kpis {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 16px; }}
    .two {{ grid-template-columns: 1.2fr .8fr; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 12px 32px rgba(0,0,0,.22); }}
    .kpi .label {{ color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .kpi .value {{ font-size: 28px; font-weight: 800; }}
    .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; color: white; }}
    .ok {{ background: var(--ok); }}
    .warn {{ background: var(--warn); color: #111827; }}
    .bad {{ background: var(--bad); }}
    .neutral {{ background: var(--neutral); }}
    .progress {{ height: 14px; background: var(--panel2); border-radius: 999px; overflow: hidden; border: 1px solid var(--line); }}
    .bar {{ height: 100%; width: min(100%, max(0%, {esc(score)}%)); background: linear-gradient(90deg, var(--bad), var(--warn), var(--ok)); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); text-align: left; font-weight: 700; }}
    code, pre {{ background: #020617; color: #d1d5db; border: 1px solid var(--line); border-radius: 10px; }}
    code {{ padding: 2px 6px; }}
    pre {{ padding: 14px; overflow: auto; max-height: 420px; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 8px 0; color: var(--text); }}
    .section {{ margin-top: 16px; }}
    .footer {{ color: var(--muted); font-size: 12px; margin-top: 24px; }}
    .pill-row {{ display:flex; flex-wrap: wrap; gap: 8px; }}
    .pill {{ background: var(--panel2); border:1px solid var(--line); border-radius:999px; padding: 8px 10px; color: var(--text); font-size: 13px; }}
    @media (max-width: 900px) {{ .kpis, .two {{ grid-template-columns: 1fr; }} main {{ padding: 16px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>ReqSys Operational Center</h1>
    <p>Painel executivo autocontido para saúde operacional, CI/CD, padrões de falha e evidências auditáveis.</p>
  </header>
  <main>
    <section class="grid kpis">
      <article class="card kpi"><div class="label">Status consolidado</div><div class="value"><span class="badge {status_class(status)}">{esc(status)}</span></div></article>
      <article class="card kpi"><div class="label">Score operacional</div><div class="value">{esc(score)}%</div><div class="progress"><div class="bar"></div></div></article>
      <article class="card kpi"><div class="label">Confiança</div><div class="value">{esc(confidence)}</div></article>
      <article class="card kpi"><div class="label">Atualização UTC</div><div class="value" style="font-size:15px">{esc(generated_at)}</div></article>
    </section>

    <section class="grid two section">
      <article class="card">
        <h2>Camadas operacionais</h2>
        <table>
          <thead><tr><th>Camada</th><th>Disponível</th><th>Status</th><th>Score</th><th>Fonte</th></tr></thead>
          <tbody>{render_layers(source_reports)}</tbody>
        </table>
      </article>
      <article class="card">
        <h2>Disponibilidade</h2>
        <h3>Camadas disponíveis</h3>
        <div class="pill-row">{''.join(f'<span class="pill">{esc(item)}</span>' for item in available_layers) or '<span class="pill">Nenhuma</span>'}</div>
        <br />
        <h3>Camadas ausentes</h3>
        <div class="pill-row">{''.join(f'<span class="pill">{esc(item)}</span>' for item in missing_layers) or '<span class="pill">Nenhuma</span>'}</div>
      </article>
    </section>

    <section class="grid two section">
      <article class="card">
        <h2>Componentes do score</h2>
        <table>
          <thead><tr><th>Componente</th><th>Score</th><th>Peso</th></tr></thead>
          <tbody>{render_components(hub.get('components', []))}</tbody>
        </table>
      </article>
      <article class="card">
        <h2>Próximas ações recomendadas</h2>
        <ul>{render_list(recommendations)}</ul>
      </article>
    </section>

    <section class="grid two section">
      <article class="card">
        <h2>Ações bloqueadas</h2>
        <ul>{render_list(blocked_actions)}</ul>
      </article>
      <article class="card">
        <h2>Limites operacionais</h2>
        <ul>{render_list(limits)}</ul>
      </article>
    </section>

    <section class="card section">
      <h2>JSON consolidado</h2>
      <pre>{esc(raw_json)}</pre>
    </section>

    <div class="footer">Gerado por <code>scripts/operational_center_html.py</code>. Zero-CDN. Artifact auditável. Não executa remediação automática.</div>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ReqSys Operational Center HTML.")
    parser.add_argument("--input", type=Path, default=Path("artifacts/operational-intelligence-hub/operational-intelligence-hub.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-center"))
    args = parser.parse_args()

    report = load_json(args.input)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / "index.html"
    output.write_text(render_html(report), encoding="utf-8")
    print(f"Operational Center HTML generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
