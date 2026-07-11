#!/usr/bin/env python3
"""Injeta a tendência de homologação do Advisor no artifact canônico do Ops Dashboard.

A implementação é offline, idempotente e estritamente report-only. A elegibilidade
indica apenas revisão humana; nunca promove gate ou produção automaticamente.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MARKER = 'id="executive-promotion-advisor-homologation-trend-card"'
CARD_KEY = "executive_promotion_advisor_homologation_trend"

SECTION = '''    <section class="card" id="executive-promotion-advisor-homologation-trend-card">
      <h2>Tendência de homologação do Advisor</h2>
      <p class="small">Evidência histórica report-only. Elegibilidade significa somente revisão humana.</p>
      <div class="grid">
        <div><div class="kpi-label">Amostras</div><div id="advisor-trend-samples" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Homologação completa</div><div id="advisor-trend-rate" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Sequência estável</div><div id="advisor-trend-streak" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Revisão humana</div><div id="advisor-trend-eligibility" class="small">obrigatória</div></div>
      </div>
      <div class="small" id="advisor-trend-detail">Aguardando histórico consolidado...</div>
      <div class="links" id="advisor-trend-links"></div>
    </section>
'''

FUNCTION = '''    function renderExecutivePromotionAdvisorHomologationTrend(payload) {
      const card = payload?.cards?.executive_promotion_advisor_homologation_trend || {};
      const samples = Number(card.sample_count ?? 0);
      const rate = Number(card.full_homologation_rate_percent ?? 0);
      const streak = Number(card.stable_streak ?? 0);
      const eligible = card.eligible_for_gate_review === true;
      const trend = card.trend || 'insufficient-data';

      document.getElementById('advisor-trend-samples').textContent = String(samples);
      document.getElementById('advisor-trend-rate').textContent = `${rate.toFixed(1)}%`;
      document.getElementById('advisor-trend-streak').textContent = String(streak);
      document.getElementById('advisor-trend-eligibility').textContent =
        eligible ? 'elegível para revisão humana' : 'ainda não elegível';
      document.getElementById('advisor-trend-detail').textContent = [
        `Tendência: ${trend}`,
        `Decisão mais recente: ${card.latest_decision || 'UNKNOWN'}`,
        'Modo: report-only',
        'Bloqueio automático: não',
      ].join(' · ');

      const links = document.getElementById('advisor-trend-links');
      links.innerHTML = '';
      const href = payload?.links?.executive_promotion_advisor_homologation_history ||
        'data/runtime-executive-index.json';
      addLink(links, 'Histórico de homologação', href);
    }
'''


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def safe_fallback() -> dict[str, Any]:
    return {
        "available": False,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "sample_count": 0,
        "artifact_pass_rate_percent": 0.0,
        "public_pass_rate_percent": 0.0,
        "full_homologation_rate_percent": 0.0,
        "stable_streak": 0,
        "latest_decision": "UNKNOWN",
        "eligible_for_gate_review": False,
        "trend": "insufficient-data",
        "source": "safe-fallback",
    }


def normalize(card: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(card or safe_fallback())
    normalized["mode"] = "report-only"
    normalized["production_blocker"] = False
    normalized["human_approval_required"] = True
    normalized["eligible_for_gate_review"] = bool(normalized.get("eligible_for_gate_review"))
    return normalized


def hydrate_contract(runtime_index: Path, trend_state: Path | None) -> str:
    runtime = load_json(runtime_index)
    if not runtime:
        raise RuntimeError(f"Runtime Executive Index ausente ou inválido: {runtime_index}")

    source_payload = load_json(trend_state) if trend_state else {}
    source_card = (source_payload.get("cards") or {}).get(CARD_KEY)
    if not isinstance(source_card, dict) or not source_card:
        source_card = (runtime.get("cards") or {}).get(CARD_KEY)
    source = str(trend_state) if isinstance(source_card, dict) and source_card else "safe-fallback"
    card = normalize(source_card if isinstance(source_card, dict) else safe_fallback())
    card["artifact_source"] = source

    runtime.setdefault("cards", {})[CARD_KEY] = card
    runtime.setdefault("links", {})[
        "executive_promotion_advisor_homologation_history"
    ] = card.get("source") or "data/runtime-executive-index.json"
    guardrails = list(runtime.get("guardrails") or [])
    for guardrail in (
        "executive_promotion_advisor_homologation_trend_report_only",
        "executive_promotion_advisor_human_approval_required",
    ):
        if guardrail not in guardrails:
            guardrails.append(guardrail)
    runtime["guardrails"] = guardrails
    runtime_index.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return source


def inject_before_pattern(text: str, pattern: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"Ponto de injeção não encontrado: {label}")
    return text[: match.start()] + insertion + text[match.start() :]


def patch_dashboard(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        text = inject_before_pattern(text, r"^[ \t]*</main>", SECTION + "\n", "seção visual")
    if "function renderExecutivePromotionAdvisorHomologationTrend(payload)" not in text:
        text = inject_before_pattern(
            text,
            r"^[ \t]*async function renderRuntimeExecutiveIndex\(\)",
            FUNCTION + "\n",
            "função de renderização",
        )
    if "renderExecutivePromotionAdvisorHomologationTrend(payload);" not in text:
        match = re.search(
            r"^(?P<indent>[ \t]*)const cards = payload\.cards \|\| fallback\.cards;",
            text,
            flags=re.MULTILINE,
        )
        if not match:
            raise RuntimeError("Hook do Runtime Executive Index não encontrado")
        hook = f"{match.group('indent')}renderExecutivePromotionAdvisorHomologationTrend(payload);\n"
        text = text[: match.start()] + hook + text[match.start() :]
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--trend-state", type=Path)
    args = parser.parse_args()
    source = hydrate_contract(args.runtime_index, args.trend_state)
    patch_dashboard(args.dashboard)
    print(json.dumps({
        "status": "patched",
        "source": source,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
