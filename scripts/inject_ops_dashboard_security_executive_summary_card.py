#!/usr/bin/env python3
"""Inject Security Executive Summary card into Ops Dashboard.

The dashboard remains static. This injector consumes only published JSON files and
keeps a safe fallback when the security summary artifact is absent.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs" / "ops-dashboard" / "index.html"

SECTION_MARKER = "security-executive-summary-card"
SCRIPT_MARKER = "renderSecurityExecutiveSummary"

SECTION = r'''

    <section class="card" id="security-executive-summary-card">
      <h2>Segurança — resumo executivo dos scanners</h2>
      <p class="small">Card executivo consumindo <code>security-executive-summary.json</code>, fonte consolidada para Gitleaks, pip-audit, npm audit e SBOM CycloneDX.</p>
      <div class="grid">
        <div><div class="kpi-label">Estado</div><div id="security-summary-state" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Score</div><div id="security-summary-score" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Risco</div><div id="security-summary-risk" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Produção bloqueada</div><div id="security-summary-production-blocked" class="kpi-value">-</div></div>
      </div>
      <div class="grid" style="margin-top: 16px;">
        <div><div class="kpi-label">Críticos</div><div id="security-summary-critical" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Altos</div><div id="security-summary-high" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Médios</div><div id="security-summary-medium" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Baixos</div><div id="security-summary-low" class="kpi-value">-</div></div>
      </div>
      <div class="links" id="security-summary-links"></div>
      <table>
        <thead><tr><th>Scanner</th><th>Disponível</th><th>Achados</th><th>Detalhe</th></tr></thead>
        <tbody id="security-summary-scanner-rows"><tr><td colspan="4">Carregando scanners...</td></tr></tbody>
      </table>
      <table>
        <thead><tr><th>Sinal executivo</th><th>Valor</th></tr></thead>
        <tbody id="security-summary-drilldown"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
      <details class="details">
        <summary>Drill-down bruto do resumo de segurança</summary>
        <pre id="security-summary-details">{}</pre>
      </details>
    </section>
'''

SCRIPT = r'''

    async function renderSecurityExecutiveSummary() {
      const fallback = {
        kind: 'security_executive_summary',
        schema_version: '1.0.0',
        mode: 'report_only',
        correlation_id: 'fallback-security-executive-summary',
        overall: {
          state: 'unknown',
          decision: 'SECURITY_EVIDENCE_MISSING',
          score: 0,
          risk_percent: 100,
          production_blocked: false,
          missing_scanners: ['gitleaks', 'pip-audit', 'npm-audit', 'cyclonedx-sbom'],
        },
        totals: {
          findings: 0,
          severity: { critical: 0, high: 0, medium: 0, low: 0, unknown: 0 },
        },
        scanners: {},
      };
      const response = await fetchOptionalJson('./data/security-executive-summary.json', fallback);
      const payload = response.data || fallback;
      const overall = payload.overall || fallback.overall;
      const totals = payload.totals || fallback.totals;
      const severity = totals.severity || fallback.totals.severity;
      const scanners = payload.scanners || {};
      const state = overall.state || 'unknown';
      const score = overall.score ?? 0;
      const risk = overall.risk_percent ?? 100;
      const blocked = Boolean(overall.production_blocked);

      document.getElementById('security-summary-state').innerHTML = `<span class="status ${statusClass(state)}">${state}</span>`;
      document.getElementById('security-summary-score').textContent = `${score}%`;
      document.getElementById('security-summary-risk').textContent = `${risk}%`;
      document.getElementById('security-summary-production-blocked').innerHTML = blocked
        ? '<span class="status critical">sim</span>'
        : '<span class="status passed">não</span>';
      document.getElementById('security-summary-critical').innerHTML = `<span class="status ${Number(severity.critical || 0) > 0 ? 'critical' : 'passed'}">${severity.critical || 0}</span>`;
      document.getElementById('security-summary-high').innerHTML = `<span class="status ${Number(severity.high || 0) > 0 ? 'warning' : 'passed'}">${severity.high || 0}</span>`;
      document.getElementById('security-summary-medium').textContent = severity.medium || 0;
      document.getElementById('security-summary-low').textContent = severity.low || 0;

      const links = document.getElementById('security-summary-links');
      links.innerHTML = '';
      addLink(links, 'security-executive-summary.json', './data/security-executive-summary.json');
      addLink(links, 'security-executive-summary.md', '../artifacts/security-executive-summary/security-executive-summary.md');

      const scannerRows = Object.values(scanners);
      document.getElementById('security-summary-scanner-rows').innerHTML = scannerRows.length
        ? scannerRows.map((scanner) => {
            const available = Boolean(scanner.available);
            const detail = scanner.components_inventory != null
              ? `componentes=${scanner.components_inventory}`
              : scanner.dependencies_evaluated != null
                ? `dependências=${scanner.dependencies_evaluated}`
                : (scanner.files || []).join(', ') || '-';
            return `
              <tr>
                <td>${scanner.scanner || '-'}</td>
                <td>${available ? '<span class="status passed">sim</span>' : '<span class="status warning">não</span>'}</td>
                <td>${scanner.findings ?? 0}</td>
                <td>${detail}</td>
              </tr>
            `;
          }).join('')
        : '<tr><td colspan="4">Nenhum scanner disponível no artifact atual.</td></tr>';

      const drilldownRows = [
        ['Decisão', overall.decision || '-'],
        ['Modo', payload.mode || '-'],
        ['Achados totais', totals.findings ?? 0],
        ['Scanners sem evidência', (overall.missing_scanners || []).join(', ') || 'nenhum'],
        ['Correlation ID', payload.correlation_id || '-'],
        ['Fonte', response.available ? response.source : `fallback: ${response.error}`],
      ];
      document.getElementById('security-summary-drilldown').innerHTML = drilldownRows.map(([label, value]) => `
        <tr><td>${label}</td><td>${value}</td></tr>
      `).join('');

      document.getElementById('security-summary-details').textContent = shortJson({
        available: response.available,
        source: response.source,
        fallback_error: response.error,
        overall,
        totals,
        scanners,
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
    html = insert_once(html, SECTION_MARKER, SECTION, "\n    <section class=\"card\" id=\"runtime-executive-post-deploy-card\">")
    html = insert_once(html, SCRIPT_MARKER, SCRIPT, "\n    async function renderRuntimeExecutivePostDeploy() {")
    html = insert_once(
        html,
        "await renderSecurityExecutiveSummary();",
        "      await renderSecurityExecutiveSummary();\n",
        "      await renderRuntimeExecutivePostDeploy();\n",
        before=True,
    )
    html = insert_once(
        html,
        "Segurança — Scanners",
        "        <a class=\"link-btn\" href=\"#security-executive-summary-card\">Segurança — Scanners</a>\n",
        "        <a class=\"link-btn\" href=\"#runtime-executive-post-deploy-card\">Runtime Executive — Post-Deploy</a>\n",
        before=True,
    )
    html = insert_once(
        html,
        "addLink(quick, 'Segurança — Scanners'",
        "      addLink(quick, 'Segurança — Scanners', '#security-executive-summary-card');\n",
        "      addLink(quick, 'Runtime Executive — Post-Deploy', '#runtime-executive-post-deploy-card');\n",
        before=True,
    )
    DASHBOARD.write_text(html, encoding="utf-8")
    print("ops dashboard security executive summary card injected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
