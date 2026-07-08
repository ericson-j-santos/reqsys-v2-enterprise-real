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
      <div class="grid" style="margin-top: 16px;">
        <div><div class="kpi-label">Disponibilidade histórica</div><div id="post-deploy-history-availability" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Latência média</div><div id="post-deploy-history-latency" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Tendência score</div><div id="post-deploy-history-score-trend" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Estabilidade</div><div id="post-deploy-history-stability" class="kpi-value">-</div></div>
      </div>
      <div class="links" id="post-deploy-links"></div>
      <table>
        <thead><tr><th>Sinal</th><th>Valor</th></tr></thead>
        <tbody id="post-deploy-drilldown"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
      <table>
        <thead><tr><th>Última execução</th><th>Estado</th><th>Score</th><th>Latência</th><th>Falhas</th></tr></thead>
        <tbody id="post-deploy-history-rows"><tr><td colspan="5">Carregando histórico...</td></tr></tbody>
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
      const historyFallback = {
        summary: {
          samples: 0,
          availability_percent: 0,
          avg_latency_ms: null,
          score_trend: 'stable',
          stability: 'unknown',
        },
        history: [],
      };
      const response = await fetchOptionalJson('./data/executive-brief.json', fallback);
      const historyResponse = await fetchOptionalJson('./data/runtime-executive-post-deploy-history.json', historyFallback);
      const payload = response.data || fallback;
      const historyPayload = historyResponse.data || historyFallback;
      const historySummary = historyPayload.summary || historyFallback.summary;
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
      document.getElementById('post-deploy-history-availability').textContent = `${historySummary.availability_percent ?? 0}%`;
      document.getElementById('post-deploy-history-latency').textContent = historySummary.avg_latency_ms == null ? '-' : `${historySummary.avg_latency_ms} ms`;
      document.getElementById('post-deploy-history-score-trend').innerHTML = `<span class="status ${statusClass(historySummary.score_trend)}">${historySummary.score_trend || 'stable'}</span>`;
      document.getElementById('post-deploy-history-stability').innerHTML = `<span class="status ${statusClass(historySummary.stability)}">${historySummary.stability || 'unknown'}</span>`;

      const links = document.getElementById('post-deploy-links');
      links.innerHTML = '';
      addLink(links, 'executive-brief.json', './data/executive-brief.json');
      addLink(links, 'histórico post-deploy', './data/runtime-executive-post-deploy-history.json');
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
        ['Histórico samples', historySummary.samples ?? 0],
        ['Disponibilidade histórica', `${historySummary.availability_percent ?? 0}%`],
        ['MTBF', historySummary.mtbf_hours == null ? '-' : `${historySummary.mtbf_hours} h`],
        ['Fonte', response.available ? response.source : `fallback: ${response.error}`],
      ];
      document.getElementById('post-deploy-drilldown').innerHTML = rows.map(([label, value]) => `
        <tr><td>${label}</td><td>${value}</td></tr>
      `).join('');

      const historyRows = (historyPayload.history || []).slice().reverse().slice(0, 6);
      document.getElementById('post-deploy-history-rows').innerHTML = historyRows.length
        ? historyRows.map((item) => `
          <tr>
            <td>${item.timestamp || '-'}</td>
            <td><span class="status ${statusClass(item.state)}">${item.state || '-'}</span></td>
            <td>${item.executive_score ?? '-'}</td>
            <td>${item.avg_latency_ms == null ? '-' : `${item.avg_latency_ms} ms`}</td>
            <td>${item.failure_count ?? '-'}</td>
          </tr>
        `).join('')
        : '<tr><td colspan="5">Nenhuma amostra histórica disponível.</td></tr>';

      document.getElementById('post-deploy-details').textContent = shortJson({
        available: response.available,
        source: response.source,
        fallback_error: response.error,
        runtime_executive_post_deploy: post,
        history_available: historyResponse.available,
        history_source: historyResponse.source,
        history_summary: historySummary,
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
