#!/usr/bin/env python3
"""Injeta o card visual do Executive Promotion Advisor no Ops Dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

MARKER = 'id="executive-promotion-advisor-card"'

SECTION = '''    <section class="card" id="executive-promotion-advisor-card">
      <h2>Executive Promotion Advisor</h2>
      <p class="small">Recomendação executiva em modo report-only, sujeita a aprovação humana.</p>
      <div class="grid">
        <div><div class="kpi-label">Decisão</div><div id="promotion-advisor-decision" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Confiança</div><div id="promotion-advisor-confidence" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Riscos</div><div id="promotion-advisor-risks" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Aprovação humana</div><div id="promotion-advisor-human-gate" class="small">obrigatória</div></div>
      </div>
      <div class="small" id="promotion-advisor-recommendation">Aguardando contrato executivo...</div>
    </section>
'''

FUNCTION = '''    function renderExecutivePromotionAdvisor(payload) {
      const card = payload?.cards?.executive_promotion_advisor || {};
      const decision = card.decision || 'REVIEW';
      const status = card.status || 'yellow';
      const confidence = Number(card.confidence_percent ?? 0);
      const risks = Array.isArray(card.risk_domains) ? card.risk_domains : [];

      document.getElementById('promotion-advisor-decision').innerHTML =
        `<span class="status ${statusClass(status)}">${decision}</span>`;
      document.getElementById('promotion-advisor-confidence').textContent =
        `${confidence.toFixed(1)}%`;
      document.getElementById('promotion-advisor-risks').textContent =
        risks.length ? String(risks.length) : '0';
      document.getElementById('promotion-advisor-human-gate').textContent =
        card.human_approval_required === false ? 'não exigida' : 'obrigatória';
      document.getElementById('promotion-advisor-recommendation').textContent =
        card.recommendation || 'Executar revisão humana antes da promoção.';
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
        text = inject_before(text, ('  </main>',), SECTION + "\n", "seção visual")

    if "function renderExecutivePromotionAdvisor(payload)" not in text:
        text = inject_before(
            text,
            ("    async function renderRuntimeExecutiveIndex()",),
            FUNCTION + "\n",
            "função de renderização",
        )

    if "renderExecutivePromotionAdvisor(payload);" not in text:
        needle = "      const cards = payload.cards || fallback.cards;"
        if needle not in text:
            raise RuntimeError("Hook do Runtime Executive Index não encontrado")
        text = text.replace(
            needle,
            "      renderExecutivePromotionAdvisor(payload);\n" + needle,
            1,
        )

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Injeta card visual do Executive Promotion Advisor")
    parser.add_argument("--dashboard", type=Path, default=Path("docs/ops-dashboard/index.html"))
    args = parser.parse_args()
    patch_dashboard(args.dashboard)
    print(f"executive_promotion_advisor_card=patched path={args.dashboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
