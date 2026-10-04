#!/usr/bin/env python3
"""Inject Runtime Executive regression alert into the main Ops Dashboard semaforo."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs" / "ops-dashboard" / "index.html"

SECTION_MARKER = "runtime-regression-alert-semaforo-card"
SCRIPT_MARKER = "renderRuntimeRegressionAlertSemaforo"

SECTION = r'''

    <section class="card" id="runtime-regression-alert-semaforo-card">
      <h2>Semáforo Executivo — Regressão temporal Runtime Executive</h2>
      <p class="small">Sinal executivo principal derivado do <code>runtime-executive-regression-alert.json</code>. Quando houver bloqueio temporal, o topo do painel reflete risco crítico de produção.</p>
      <div class="grid">
        <div><div class="kpi-label">Regression alert</div><div id="semaforo-regression-status" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Risco temporal</div><div id="semaforo-regression-risk" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Produção bloqueada</div><div id="semaforo-regression-blocked" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Violations</div><div id="semaforo-regression-violations" class="kpi-value">-</div></div>
      </div>
      <div class="links" id="semaforo-regression-links"></div>
      <details class="details">
        <summary>Drill-down do semáforo temporal</summary>
        <pre id="semaforo-regression-details">{}</pre>
      </details>
    </section>
'''

SCRIPT = r'''

    async function renderRuntimeRegressionAlertSemaforo() {
      const fallback = {
        status: 'unknown',
        risk: 'unknown',
        production_blocked: false,
        violations: [],
        observed: {},
        thresholds: {},
      };
      const response = await fetchOptionalJson('../artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json', fallback);
      const alert = response.data || fallback;
      const status = alert.status || 'unknown';
      const risk = alert.risk || 'unknown';
      const blocked = Boolean(alert.production_blocked);
      const violations = alert.violations || [];

      document.getElementById('semaforo-regression-status').innerHTML = `<span class="status ${statusClass(status)}">${status}</span>`;
      document.getElementById('semaforo-regression-risk').innerHTML = `<span class="status ${statusClass(risk)}">${risk}</span>`;
      document.getElementById('semaforo-regression-blocked').innerHTML = blocked
        ? '<span class="status critical">sim</span>'
        : '<span class="status passed">não</span>';
      document.getElementById('semaforo-regression-violations').textContent = violations.length;

      if (blocked) {
        document.getElementById('overall').innerHTML = '<span class="status blocked">blocked</span>';
        document.getElementById('critical').textContent = Math.max(Number(document.getElementById('critical').textContent || 0), violations.length || 1);
      }

      const links = document.getElementById('semaforo-regression-links');
      links.innerHTML = '';
      addLink(links, 'Regression alert JSON', '../artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json');
      addLink(links, 'Runtime Executive Post-Deploy', '#runtime-executive-post-deploy-card');

      document.getElementById('semaforo-regression-details').textContent = shortJson({
        available: response.available,
        source: response.source,
        fallback_error: response.error,
        status,
        risk,
        production_blocked: blocked,
        violations,
        observed: alert.observed || {},
        thresholds: alert.thresholds || {},
      });
    }
'''


def insert_once(content: str, marker: str, payload: str, anchor: str, *, before: bool = True) -> str:
    if marker in content:
        return content
    if anchor not in content:
        raise SystemExit(f"anchor não encontrado para injeção: {anchor}")
    return content.replace(anchor, payload + anchor if before else anchor + payload, 1)


def main() -> int:
    html = DASHBOARD.read_text(encoding="utf-8")
    html = insert_once(html, SECTION_MARKER, SECTION, "\n    <section class=\"card\">\n      <h2>Runtime Executive Index — visão pública consolidada</h2>")
    html = insert_once(html, SCRIPT_MARKER, SCRIPT, "\n    async function loadDashboard() {")
    html = insert_once(
        html,
        "await renderRuntimeRegressionAlertSemaforo();",
        "      await renderRuntimeRegressionAlertSemaforo();\n",
        "      await renderRuntimeExecutiveIndex();\n",
        before=True,
    )
    DASHBOARD.write_text(html, encoding="utf-8")
    print("ops dashboard regression alert semaforo injected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
