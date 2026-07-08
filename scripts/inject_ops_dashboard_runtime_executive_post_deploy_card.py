#!/usr/bin/env python3
"""Inject Runtime Executive post-deploy card into Ops Dashboard.

The dashboard remains a static artifact. This injector is deterministic and runs
before publishing docs/ops-dashboard as the ops-dashboard-static artifact.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs" / "ops-dashboard" / "index.html"

SECTION_MARKER = "runtime-executive-post-deploy-card"
SCRIPT_MARKER = "renderRuntimeExecutivePostDeploy"

SECTION = r'''

    <section class="card" id="runtime-executive-post-deploy-card">
      <h2>Runtime Executive — Post-Deploy público</h2>
      <p class="small">Card dedicado ao domínio <code>runtime_executive_post_deploy</code>, consumindo o <code>executive-brief.json</code> gerado pelo Estado Único.</p>
      <div class="grid">
        <div><div class="kpi-label">Estado público</div><div id="post-deploy-state" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Score</div><div id="post-deploy-score" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Falhas</div><div id="post-deploy-failures" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Produção</div><div id="post-deploy-production" class="kpi-value">-</div></div>
      </div>
      <div class="links" id="post-deploy-links"></div>
      <table>
        <thead><tr><th>Sinal</th><th>Valor</th></tr></thead>
        <tbody id="post-deploy-drilldown"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
      <details class="details">
        <summary>Drill-down bruto do post-deploy</summary>
        <pre id="post-deploy-details">{}</pre>
      </details>
    </section>
'''

SCRIPT = r'''

    async function renderRuntimeExecutivePostDeploy() {
      const fallback = {
        estado_unico: {
          pronto_para_producao: false,
          runtime_executive_post_deploy: {
            state: 'unknown',
            score: 0,
            failure_count: 0,
            page_url: '',
            contract_url: '',
          },
        },
        links: {},
        semaforo_executivo: {},
        indicadores_executivos: {},
      };
      const response = await fetchOptionalJson('./data/executive-brief.json', fallback);
      const payload = response.data || fallback;
      const estado = payload.estado_unico || {};
      const post = estado.runtime_executive_post_deploy || fallback.estado_unico.runtime_executive_post_deploy;
      const state = post.state || payload.semaforo_executivo?.runtime_executive_publico || 'unknown';
      const score = post.score ?? payload.indicadores_executivos?.runtime_executive_post_deploy_percent ?? 0;
      const failures = post.failure_count ?? 0;
      const productionReady = Boolean(estado.pronto_para_producao);

      document.getElementById('post-deploy-state').innerHTML = `<span class="status ${statusClass(state)}">${state}</span>`;
      document.getElementById('post-deploy-score').textContent = `${score}%`;
      document.getElementById('post-deploy-failures').textContent = failures;
      document.getElementById('post-deploy-production').innerHTML = productionReady
        ? '<span class="status passed">ready</span>'
        : '<span class="status warning">pendente</span>';

      const links = document.getElementById('post-deploy-links');
      links.innerHTML = '';
      addLink(links, 'executive-brief.json', './data/executive-brief.json');
      if (post.page_url) addLink(links, 'Página pública', post.page_url, true);
      if (post.contract_url) addLink(links, 'Contrato público', post.contract_url, true);
      if (payload.links?.runtime_executive_public_page && payload.links.runtime_executive_public_page !== post.page_url) {
        addLink(links, 'Página pública — brief', payload.links.runtime_executive_public_page, true);
      }
      if (payload.links?.runtime_executive_public_contract && payload.links.runtime_executive_public_contract !== post.contract_url) {
        addLink(links, 'Contrato público — brief', payload.links.runtime_executive_public_contract, true);
      }

      const rows = [
        ['Page URL', post.page_url || '-'],
        ['Contract URL', post.contract_url || '-'],
        ['Estado', state],
        ['Score', `${score}%`],
        ['Failures', failures],
        ['Semáforo', payload.semaforo_executivo?.runtime_executive_publico || '-'],
        ['Produção pronta', productionReady ? 'sim' : 'não'],
        ['Fonte', response.available ? response.source : `fallback: ${response.error}`],
      ];
      document.getElementById('post-deploy-drilldown').innerHTML = rows.map(([label, value]) => `
        <tr><td>${label}</td><td>${value}</td></tr>
      `).join('');

      document.getElementById('post-deploy-details').textContent = shortJson({
        available: response.available,
        source: response.source,
        fallback_error: response.error,
        runtime_executive_post_deploy: post,
        semaforo_executivo: payload.semaforo_executivo || {},
        indicadores_executivos: payload.indicadores_executivos || {},
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
    html = insert_once(html, SECTION_MARKER, SECTION, "\n    <section class=\"card\">\n      <h2>Runtime público — readiness Fly/DuckDNS</h2>")
    html = insert_once(html, SCRIPT_MARKER, SCRIPT, "\n    async function renderMergeIntelligence() {")
    html = insert_once(
        html,
        "await renderRuntimeExecutivePostDeploy();",
        "      await renderRuntimeExecutivePostDeploy();\n",
        "      await renderRuntimeExecutiveIndex();\n",
        before=False,
    )
    html = insert_once(
        html,
        "Runtime Executive — Post-Deploy",
        "        <a class=\"link-btn\" href=\"#runtime-executive-post-deploy-card\">Runtime Executive — Post-Deploy</a>\n",
        "        <a class=\"link-btn\" href=\"#trilha-d-history-card\">Trilha D — Histórico</a>\n",
        before=True,
    )
    html = insert_once(
        html,
        "addLink(quick, 'Runtime Executive — Post-Deploy'",
        "      addLink(quick, 'Runtime Executive — Post-Deploy', '#runtime-executive-post-deploy-card');\n",
        "      addLink(quick, `Trilha D — score ${trilhaScore}`, '#trilha-d-history-card');\n",
        before=True,
    )
    DASHBOARD.write_text(html, encoding="utf-8")
    print("ops dashboard runtime executive post-deploy card injected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
