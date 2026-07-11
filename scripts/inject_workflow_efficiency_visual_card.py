#!/usr/bin/env python3
"""Injeta os cards Workflow Efficiency e Executive Promotion Advisor no Ops Dashboard.

O pipeline canônico continua offline e report-only. Quando uma evidência consolidada
do Advisor estiver disponível, ela prevalece; na ausência, publica fallback REVIEW
seguro e explicitamente não bloqueante.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.inject_executive_promotion_advisor_card import patch_dashboard as patch_advisor_dashboard

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

ADVISOR_CANDIDATES = (
    Path("artifacts/executive-promotion-advisor-state/runtime-executive-index.json"),
    Path("artifacts/executive-promotion-advisor/executive-promotion-advisor.json"),
)


def inject_before(text: str, needles: tuple[str, ...], insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    for needle in needles:
        if needle in text:
            return text.replace(needle, insertion + needle, 1)
    raise RuntimeError(f"Ponto de injeção não encontrado: {label}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def resolve_advisor_card(runtime_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    current = (runtime_payload.get("cards") or {}).get("executive_promotion_advisor")
    if isinstance(current, dict) and current:
        return current, "runtime-index"

    for candidate in ADVISOR_CANDIDATES:
        payload = load_json(candidate)
        card = (payload.get("cards") or {}).get("executive_promotion_advisor")
        if not card and payload.get("decision") in {"READY", "REVIEW", "HOLD"}:
            card = payload
        if isinstance(card, dict) and card:
            return card, str(candidate)

    return {
        "status": "yellow",
        "decision": "REVIEW",
        "confidence_percent": 40.0,
        "risk_domains": ["advisor_evidence_unavailable"],
        "recommendation": "Aguardar evidência consolidada e executar revisão humana antes da promoção.",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "available": False,
    }, "safe-fallback"


def hydrate_advisor_contract(runtime_index: Path) -> str:
    payload = load_json(runtime_index)
    if not payload:
        raise RuntimeError(f"Runtime Executive Index ausente ou inválido: {runtime_index}")
    card, source = resolve_advisor_card(payload)
    card = dict(card)
    card["mode"] = "report-only"
    card["production_blocker"] = False
    card["human_approval_required"] = True
    card["source"] = source
    payload.setdefault("cards", {})["executive_promotion_advisor"] = card
    payload.setdefault("links", {})["executive_promotion_advisor"] = "data/runtime-executive-index.json"
    guardrails = list(payload.get("guardrails") or [])
    for item in ("executive_promotion_advisor_report_only", "executive_promotion_human_gate"):
        if item not in guardrails:
            guardrails.append(item)
    payload["guardrails"] = guardrails
    runtime_index.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return source


def patch_dashboard(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text = inject_before(
            text,
            ('    <section class="card">\n      <h2>Runtime público — readiness Fly/DuckDNS</h2>', '  </main>'),
            SECTION + "\n",
            "seção visual",
        )
    if "function renderWorkflowEfficiency(payload)" not in text:
        text = inject_before(text, ("    async function renderRuntimeExecutiveIndex()",), FUNCTION + "\n", "função de renderização")
    if "renderWorkflowEfficiency(payload);" not in text:
        needle = "      const cards = payload.cards || fallback.cards;"
        if needle not in text:
            raise RuntimeError("Hook do Runtime Executive Index não encontrado")
        text = text.replace(needle, "      renderWorkflowEfficiency(payload);\n" + needle, 1)
    path.write_text(text, encoding="utf-8")
    patch_advisor_dashboard(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Injeta cards Workflow Efficiency e Promotion Advisor")
    parser.add_argument("--dashboard", type=Path, default=Path("docs/ops-dashboard/index.html"))
    parser.add_argument("--runtime-index", type=Path, default=Path("docs/ops-dashboard/data/runtime-executive-index.json"))
    args = parser.parse_args()
    source = hydrate_advisor_contract(args.runtime_index)
    patch_dashboard(args.dashboard)
    print(f"workflow_efficiency_visual_card=patched path={args.dashboard}")
    print(f"executive_promotion_advisor_card=patched source={source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
