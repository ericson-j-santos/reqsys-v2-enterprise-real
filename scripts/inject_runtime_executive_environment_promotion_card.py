#!/usr/bin/env python3
"""Injeta card visual de promoção DEV/STG/PROD nos painéis estáticos.

Consome somente `cards.environment_promotion_readiness` já publicado no
`runtime-executive-index.json`. Não realiza chamadas externas, não lê secrets e
mantém o runtime público estático.
"""

from __future__ import annotations

from pathlib import Path

OPS_DASHBOARD = Path("docs/ops-dashboard/index.html")
RUNTIME_EXECUTIVE = Path("docs/ops-dashboard/runtime-executive.html")
MARKER = "environment-promotion-readiness-visual-card"

OPS_SECTION = """
    <section class="card" id="environment-promotion-readiness-visual-card">
      <h2>Promoção DEV → STG → PROD</h2>
      <p class="small">Semáforo executivo consumindo <code>cards.environment_promotion_readiness</code> do <code>runtime-executive-index.json</code>. O runtime público usa apenas artefatos estáticos.</p>
      <div class="grid">
        <div><div class="kpi-label">Decisão de promoção</div><div id="env-promotion-decision" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Pronto para PROD</div><div id="env-promotion-ready" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Cobertura</div><div id="env-promotion-coverage" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Blockers</div><div id="env-promotion-blockers" class="kpi-value">-</div></div>
      </div>
      <table>
        <thead><tr><th>Indicador</th><th>Valor</th></tr></thead>
        <tbody id="env-promotion-rows"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
      <div class="links" id="env-promotion-links"></div>
    </section>
"""

OPS_FUNCTION = """
    function renderEnvironmentPromotionReadiness(payload) {
      const summary = payload.summary || {};
      const card = (payload.cards || {}).environment_promotion_readiness || {};
      const decision = card.decision || summary.environment_promotion_decision || 'UNKNOWN';
      const ready = Boolean(card.ready_for_prod_promotion || summary.environment_promotion_ready);
      const coverage = card.coverage_percent ?? summary.environment_promotion_coverage_percent ?? 0;
      const blockers = Array.isArray(card.production_blockers) ? card.production_blockers : [];
      const required = Array.isArray(card.required_environments) ? card.required_environments : ['dev', 'stg', 'prod'];
      const readyEnvs = Array.isArray(card.ready_environments) ? card.ready_environments : [];
      const missing = Array.isArray(card.missing_environments) ? card.missing_environments : [];
      const failed = Array.isArray(card.failed_environments) ? card.failed_environments : [];

      document.getElementById('env-promotion-decision').innerHTML = `<span class="status ${statusClass(decision)}">${decision}</span>`;
      document.getElementById('env-promotion-ready').innerHTML = ready ? '<span class="status passed">SIM</span>' : '<span class="status blocked">NÃO</span>';
      document.getElementById('env-promotion-coverage').textContent = `${coverage}%`;
      document.getElementById('env-promotion-blockers').textContent = card.blocker_count ?? blockers.length;
      document.getElementById('env-promotion-rows').innerHTML = [
        ['Status', `<span class="status ${statusClass(card.status)}">${card.status || 'unknown'}</span>`],
        ['Risco', `<span class="status ${statusClass(card.risk)}">${card.risk || 'unknown'}</span>`],
        ['Ambientes exigidos', required.join(', ') || '-'],
        ['Ambientes verdes', readyEnvs.join(', ') || '-'],
        ['Ambientes sem evidência', missing.join(', ') || '-'],
        ['Ambientes com falha', failed.join(', ') || '-'],
        ['Blockers ativos', blockers.join(', ') || 'nenhum'],
        ['Fonte', card.source_artifact || 'environment-promotion-readiness'],
      ].map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join('');

      const links = document.getElementById('env-promotion-links');
      links.innerHTML = '';
      addLink(links, 'runtime-executive-index.json', './data/runtime-executive-index.json');
      if (payload.links?.environment_promotion_readiness) addLink(links, 'Environment Promotion Readiness', payload.links.environment_promotion_readiness);
    }
"""

RUNTIME_SECTION = """
    <section class="card" id="environment-promotion-readiness-visual-card">
      <h2>Promoção de ambientes</h2>
      <p class="small">Semáforo DEV/STG/PROD para promoção produtiva. Consome o card <code>environment_promotion_readiness</code> presente no contrato público.</p>
      <div class="grid" aria-label="Promoção de ambientes">
        <div><div class="kpi-label">Decisão</div><div id="runtime-env-promotion-decision" class="kpi-value">-</div></div>
        <div><div class="kpi-label">PROD</div><div id="runtime-env-promotion-ready" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Cobertura</div><div id="runtime-env-promotion-coverage" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Blockers</div><div id="runtime-env-promotion-blockers" class="kpi-value">-</div></div>
      </div>
      <table>
        <thead><tr><th>Indicador</th><th>Valor</th></tr></thead>
        <tbody id="runtime-env-promotion-rows"><tr><td colspan="2">Carregando...</td></tr></tbody>
      </table>
    </section>
"""

RUNTIME_FUNCTION = """
    function renderEnvironmentPromotion(payload) {
      const summary = payload.summary || {};
      const card = (payload.cards || {}).environment_promotion_readiness || {};
      const decision = card.decision || summary.environment_promotion_decision || 'UNKNOWN';
      const ready = Boolean(card.ready_for_prod_promotion || summary.environment_promotion_ready);
      const coverage = card.coverage_percent ?? summary.environment_promotion_coverage_percent ?? 0;
      const blockers = Array.isArray(card.production_blockers) ? card.production_blockers : [];
      const readyEnvs = Array.isArray(card.ready_environments) ? card.ready_environments : [];
      const missing = Array.isArray(card.missing_environments) ? card.missing_environments : [];
      const failed = Array.isArray(card.failed_environments) ? card.failed_environments : [];

      document.getElementById('runtime-env-promotion-decision').innerHTML = badge(decision);
      document.getElementById('runtime-env-promotion-ready').innerHTML = badge(ready ? 'ready' : 'blocked');
      document.getElementById('runtime-env-promotion-coverage').textContent = `${coverage}%`;
      document.getElementById('runtime-env-promotion-blockers').textContent = card.blocker_count ?? blockers.length;
      document.getElementById('runtime-env-promotion-rows').innerHTML = [
        ['Status', badge(card.status || 'unknown')],
        ['Risco', badge(card.risk || 'unknown')],
        ['Ambientes verdes', readyEnvs.join(', ') || '-'],
        ['Ambientes sem evidência', missing.join(', ') || '-'],
        ['Ambientes com falha', failed.join(', ') || '-'],
        ['Blockers ativos', blockers.join(', ') || 'nenhum'],
        ['Fonte', card.source_artifact || 'environment-promotion-readiness'],
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
        text = inject_once(text, "    <section class=\"card\" id=\"executive-readiness-visual-card\">", OPS_SECTION + "\n", "ops section")
    if "function renderEnvironmentPromotionReadiness(payload)" not in text:
        text = inject_once(text, "    function renderExecutiveReadinessVisual(payload)", OPS_FUNCTION + "\n", "ops function")
    if "renderEnvironmentPromotionReadiness(payload);" not in text:
        text = text.replace("      renderExecutiveReadinessVisual(payload);", "      renderEnvironmentPromotionReadiness(payload);\n      renderExecutiveReadinessVisual(payload);", 1)
    path.write_text(text, encoding="utf-8")


def patch_runtime_executive(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text = inject_once(text, "    <section class=\"card\" id=\"executive-readiness-visual-card\">", RUNTIME_SECTION + "\n", "runtime section")
    if "function renderEnvironmentPromotion(payload)" not in text:
        text = inject_once(text, "    function renderExecutiveReadiness(payload)", RUNTIME_FUNCTION + "\n", "runtime function")
    if "renderEnvironmentPromotion(payload);" not in text:
        text = text.replace("        renderExecutiveReadiness(payload);", "        renderEnvironmentPromotion(payload);\n        renderExecutiveReadiness(payload);", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_ops_dashboard(OPS_DASHBOARD)
    patch_runtime_executive(RUNTIME_EXECUTIVE)
    print("Environment Promotion visual cards injected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
