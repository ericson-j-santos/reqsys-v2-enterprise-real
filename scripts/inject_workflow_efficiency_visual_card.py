#!/usr/bin/env python3
"""Injeta o card visual Workflow Efficiency no Ops Dashboard.

O card consome exclusivamente ``runtime-executive-index.json``. Nenhuma métrica
é recalculada no navegador e nenhuma chamada externa é realizada.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MARKER = 'id="workflow-efficiency-visual-card"'

SECTION = '''    <section class="card" id="workflow-efficiency-visual-card">
      <h2>Workflow Efficiency</h2>
      <p class="small">Indicador executivo consumido exclusivamente de <code>runtime-executive-index.json</code>.</p>
      <div class="grid">
        <div><div class="kpi-label">Score</div><div id="workflow-efficiency-score" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Tendência</div><div id="workflow-efficiency-trend" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Execuções evitáveis</div><div id="workflow-efficiency-savings" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Próxima ação</div><div id="workflow-efficiency-action" class="small">-</div></div>
      </div>
      <div class="small" id="workflow-efficiency-detail">Aguardando contrato executivo...</div>
      <div class="links" id="workflow-efficiency-links"></div>
    </section>
'''

FUNCTION = '''    function renderWorkflowEfficiency(payload) {
      const card = payload?.cards?.workflow_efficiency || {};
      const score = Number(card.score_percent ?? 0);
      const trend = Number(card.trend_delta_points ?? 0);
      const status = card.status || 'unknown';

      document.getElementById('workflow-efficiency-score').innerHTML =
        `<span class="status ${statusClass(status)}">${score.toFixed(1)}%</span>`;
      document.getElementById('workflow-efficiency-trend').textContent =
        `${trend >= 0 ? '+' : ''}${trend.toFixed(1)} pts`;
      document.getElementById('workflow-efficiency-savings').textContent =
        card.estimated_runs_saved ?? '-';
      document.getElementById('workflow-efficiency-action').textContent =
        card.recommended_action || 'KEEP_MEASURING';
      document.getElementById('workflow-efficiency-detail').textContent = [
        card.top_workflow ? `Workflow prioritário: ${card.top_workflow}` : '',
        card.pr_sample_count != null ? `Amostra: ${card.pr_sample_count} PRs` : '',
        card.mode ? `Modo: ${card.mode}` : '',
      ].filter(Boolean).join(' · ') || 'Contrato ainda não disponível.';

      const links = document.getElementById('workflow-efficiency-links');
      links.innerHTML = '';
      const href = payload?.links?.workflow_efficiency || 'data/ci-workflow-efficiency-dashboard.json';
      addLink(links, 'Contrato Workflow Efficiency', href);
    }
'''


def inject_before(text: str, needles: tuple[str, ...], insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    for needle in needles:
        if needle in text:
            return text.replace(needle, insertion + needle, 1)
    raise RuntimeError(f"Ponto de injeção não encontrado: {label}")


def patch_dashboard(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    if MARKER not in text:
        text = inject_before(
            text,
            (
                '    <section class="card">\n      <h2>Runtime público — readiness Fly/DuckDNS</h2>',
                '  </main>',
            ),
            SECTION + "\n",
            "seção visual",
        )

    if "function renderWorkflowEfficiency(payload)" not in text:
        text = inject_before(
            text,
            ("    async function renderRuntimeExecutiveIndex()",),
            FUNCTION + "\n",
            "função de renderização",
        )

    if "renderWorkflowEfficiency(payload);" not in text:
        needle = "      const cards = payload.cards || fallback.cards;"
        if needle not in text:
            raise RuntimeError("Hook do Runtime Executive Index não encontrado")
        text = text.replace(
            needle,
            "      renderWorkflowEfficiency(payload);\n" + needle,
            1,
        )

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Injeta card visual Workflow Efficiency")
    parser.add_argument("--dashboard", type=Path, default=Path("docs/ops-dashboard/index.html"))
    args = parser.parse_args()
    patch_dashboard(args.dashboard)
    print(f"workflow_efficiency_visual_card=patched path={args.dashboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
