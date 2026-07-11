#!/usr/bin/env python3
"""Injeta cards visuais de Executive Readiness nos painéis estáticos."""

from __future__ import annotations

from pathlib import Path

OPS_DASHBOARD = Path("docs/ops-dashboard/index.html")
RUNTIME_EXECUTIVE = Path("docs/ops-dashboard/runtime-executive.html")
MARKER = "executive-readiness-visual-card"

OPS_SECTION = """
    <section class="card" id="executive-readiness-visual-card">
      <h2>Executive Readiness — decisão de produção</h2>
      <p class="small">Visão executiva consumindo <code>cards.executive_readiness</code> do <code>runtime-executive-index.json</code>. A decisão é report-only e preserva o Estado Único como fonte de verdade.</p>
      <div class="grid">
        <div><div class="kpi-label">Decisão executiva</div><div id="exec-readiness-decision" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Production ready</div><div id="exec-readiness-production-ready" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Score readiness</div><div id="exec-readiness-score" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Blockers</div><div id="exec-readiness-blockers-count" class="kpi-value">-</div></div>
      </div>
      <table>
        <thead><tr><th>Campo</th><th>Valor</th></tr></thead>
        <tbody id="exec-readiness-details-rows"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
      <div class="links" id="exec-readiness-links"></div>
    </section>
"""

OPS_FUNCTION = """
    function renderExecutiveReadinessVisual(payload) {
      const summary = payload.summary || {};
      const card = (payload.cards || {}).executive_readiness || {};
      const decision = card.decision || summary.executive_readiness_decision || 'UNKNOWN';
      const productionReady = Boolean(summary.production_ready || card.ready_for_production);
      const risk = card.risk || summary.risk || 'unknown';
      const blockers = Array.isArray(card.blockers) ? card.blockers : [];

      document.getElementById('exec-readiness-decision').innerHTML = `<span class="status ${statusClass(decision)}">${decision}</span>`;
      document.getElementById('exec-readiness-production-ready').innerHTML = productionReady ? '<span class="status passed">SIM</span>' : '<span class="status blocked">NÃO</span>';
      document.getElementById('exec-readiness-score').textContent = `${card.score ?? summary.executive_score ?? 0}%`;
      document.getElementById('exec-readiness-blockers-count').textContent = card.blocker_count ?? blockers.length ?? 0;

      document.getElementById('exec-readiness-details-rows').innerHTML = [
        ['Risco', `<span class="status ${statusClass(risk)}">${risk}</span>`],
        ['Risk percent', `${card.risk_percent ?? '-'}%`],
        ['Status', `<span class="status ${statusClass(card.status)}">${card.status || 'unknown'}</span>`],
        ['Domínios obrigatórios', (card.required_domains || []).join(', ') || '-'],
        ['Blockers ativos', blockers.join(', ') || 'nenhum'],
        ['Fonte', card.source_artifact || 'executive-readiness-gate'],
      ].map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join('');

      const links = document.getElementById('exec-readiness-links');
      links.innerHTML = '';
      addLink(links, 'runtime-executive-index.json', './data/runtime-executive-index.json');
      if (payload.links?.executive_readiness_gate) addLink(links, 'Executive Readiness Gate', payload.links.executive_readiness_gate);
      if (payload.links?.executive_brief) addLink(links, 'Executive Brief', payload.links.executive_brief);
    }
"""

RUNTIME_SECTION = """
    <section class="card" id="executive-readiness-visual-card">
      <h2>Executive Readiness</h2>
      <p class="small">Decisão consolidada de produção baseada no Estado Único. Este bloco consome o card <code>executive_readiness</code> já presente no contrato público.</p>
      <div class="grid" aria-label="Executive readiness">
        <div><div class="kpi-label">Decisão</div><div id="readiness-decision" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Produção</div><div id="readiness-production" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Score</div><div id="readiness-score" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Blockers</div><div id="readiness-blockers" class="kpi-value">-</div></div>
      </div>
      <table>
        <thead><tr><th>Indicador</th><th>Valor</th></tr></thead>
        <tbody id="readiness-rows"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
    </section>
"""

RUNTIME_FUNCTION = """
    function renderExecutiveReadiness(payload) {
      const summary = payload.summary || {};
      const card = (payload.cards || {}).executive_readiness || {};
      const decision = card.decision || summary.executive_readiness_decision || 'UNKNOWN';
      const productionReady = Boolean(summary.production_ready || card.ready_for_production);
      const blockers = Array.isArray(card.blockers) ? card.blockers : [];
      const risk = card.risk || summary.risk || 'unknown';

      document.getElementById('readiness-decision').innerHTML = badge(decision);
      document.getElementById('readiness-production').innerHTML = badge(productionReady ? 'ready' : 'blocked');
      document.getElementById('readiness-score').textContent = `${card.score ?? summary.executive_score ?? 0}%`;
      document.getElementById('readiness-blockers').textContent = card.blocker_count ?? blockers.length ?? 0;
      document.getElementById('readiness-rows').innerHTML = [
        ['Risco', badge(risk)],
        ['Risk percent', `${card.risk_percent ?? '-'}%`],
        ['Status', badge(card.status || 'unknown')],
        ['Domínios obrigatórios', (card.required_domains || []).join(', ') || '-'],
        ['Blockers ativos', blockers.join(', ') || 'nenhum'],
        ['Fonte', card.source_artifact || 'executive-readiness-gate'],
      ].map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join('');
    }
"""


def inject_once(text: str, needle: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    if needle not in text:
        raise RuntimeError(f"Ponto de injeção não encontrado: {label}")
    return text.replace(needle, insertion + needle, 1)


def patch_ops_dashboard(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text = inject_once(text, "    <section class=\"card\">\n      <h2>Runtime público", OPS_SECTION + "\n", "ops section")
    if "function renderExecutiveReadinessVisual(payload)" not in text:
        text = inject_once(text, "    function renderMergeIntelligence()", OPS_FUNCTION + "\n", "ops function")
    if "renderExecutiveReadinessVisual(payload);" not in text:
        text = text.replace("      const payload = response.data || fallback;\n      const cards = payload.cards || fallback.cards;", "      const payload = response.data || fallback;\n      renderExecutiveReadinessVisual(payload);\n      const cards = payload.cards || fallback.cards;", 1)
    path.write_text(text, encoding="utf-8")


def patch_runtime_executive(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text = inject_once(text, "    <section class=\"card\">\n      <h2>Produção e governança", RUNTIME_SECTION + "\n", "runtime section")
    if "function renderExecutiveReadiness(payload)" not in text:
        text = inject_once(text, "    function renderCards(cards) {", RUNTIME_FUNCTION + "\n", "runtime function")
    if "renderExecutiveReadiness(payload);" not in text:
        text = text.replace("        setText('summary-confidence', summary.confidence);\n        renderCards(payload.cards || {});", "        setText('summary-confidence', summary.confidence);\n        renderExecutiveReadiness(payload);\n        renderCards(payload.cards || {});", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_ops_dashboard(OPS_DASHBOARD)
    patch_runtime_executive(RUNTIME_EXECUTIVE)
    print("Executive Readiness visual cards injected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
