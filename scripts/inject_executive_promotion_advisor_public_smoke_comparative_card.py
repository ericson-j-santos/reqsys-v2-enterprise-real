#!/usr/bin/env python3
"""Injeta o comparativo público DEV/STG/PROD do Advisor no Ops Dashboard.

Execução offline e estritamente report-only. O script consome apenas artifacts locais,
preserva decisões existentes e nunca promove produção automaticamente.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CARD_KEY = "executive_promotion_advisor_public_smoke_comparative"
MARKER = 'id="executive-promotion-advisor-public-smoke-comparative-card"'

SECTION = '''    <section class="card" id="executive-promotion-advisor-public-smoke-comparative-card">
      <h2>Advisor — comparação pública DEV/STG/PROD</h2>
      <p class="small">Visão executiva report-only, sujeita a aprovação humana.</p>
      <div class="grid">
        <div><div class="kpi-label">Cobertura</div><div id="advisor-public-comparative-coverage" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Taxa ponderada</div><div id="advisor-public-comparative-rate" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Menor taxa</div><div id="advisor-public-comparative-min-rate" class="kpi-value">-</div></div>
        <div><div class="kpi-label">Tendência</div><div id="advisor-public-comparative-trend" class="small">-</div></div>
      </div>
      <div class="small" id="advisor-public-comparative-environments">Aguardando Estado Único...</div>
      <div class="small" id="advisor-public-comparative-human-gate">Aprovação humana obrigatória.</div>
    </section>
'''

FUNCTION = '''    function renderExecutivePromotionAdvisorPublicSmokeComparative(payload) {
      const card = payload?.cards?.executive_promotion_advisor_public_smoke_comparative || {};
      const environmentCount = Number(card.environment_count ?? 0);
      const requiredCount = Number(card.required_environment_count ?? 3);
      const weightedRate = Number(card.weighted_pass_rate_percent ?? 0);
      const minimumRate = Number(card.minimum_pass_rate_percent ?? 0);
      const trend = card.trend || 'insufficient-environment-coverage';
      const environments = card.environments || {};

      document.getElementById('advisor-public-comparative-coverage').textContent =
        `${environmentCount}/${requiredCount}`;
      document.getElementById('advisor-public-comparative-rate').textContent =
        `${weightedRate.toFixed(1)}%`;
      document.getElementById('advisor-public-comparative-min-rate').textContent =
        `${minimumRate.toFixed(1)}%`;
      document.getElementById('advisor-public-comparative-trend').textContent = trend;

      const labels = ['dev', 'stg', 'prod'].map((name) => {
        const item = environments[name] || {};
        const rate = Number(item.pass_rate_percent ?? 0).toFixed(1);
        const samples = Number(item.sample_count ?? 0);
        return `${name.toUpperCase()}: ${rate}% (${samples})`;
      });
      document.getElementById('advisor-public-comparative-environments').textContent = labels.join(' · ');
      document.getElementById('advisor-public-comparative-human-gate').textContent =
        card.human_approval_required === false
          ? 'Contrato inválido: aprovação humana ausente.'
          : 'Aprovação humana obrigatória; sem promoção automática.';
    }
'''


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def resolve_card(state_path: Path) -> tuple[dict[str, Any], str]:
    state = load_json(state_path)
    card = (state.get("cards") or {}).get(CARD_KEY)
    if isinstance(card, dict) and card:
        return dict(card), str(state_path)
    return {
        "available": False,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "environment_count": 0,
        "required_environment_count": 3,
        "complete_environment_coverage": False,
        "weighted_pass_rate_percent": 0.0,
        "minimum_pass_rate_percent": 0.0,
        "minimum_stable_streak": 0,
        "trend": "insufficient-environment-coverage",
        "eligible_for_human_review": False,
        "environments": {},
    }, "safe-fallback"


def hydrate_runtime_index(runtime_index: Path, state_path: Path) -> str:
    payload = load_json(runtime_index)
    if not payload:
        raise RuntimeError(f"Runtime Executive Index ausente ou inválido: {runtime_index}")
    card, source = resolve_card(state_path)
    card["mode"] = "report-only"
    card["production_blocker"] = False
    card["human_approval_required"] = True
    card["source"] = source
    card["eligible_for_human_review"] = bool(card.get("eligible_for_human_review"))
    card["complete_environment_coverage"] = bool(card.get("complete_environment_coverage"))

    payload.setdefault("cards", {})[CARD_KEY] = card
    payload.setdefault("links", {})[CARD_KEY] = "data/runtime-executive-index.json"
    guardrails = list(payload.get("guardrails") or [])
    marker = "executive_promotion_advisor_public_smoke_comparative_report_only"
    if marker not in guardrails:
        guardrails.append(marker)
    payload["guardrails"] = guardrails
    runtime_index.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    if "function renderExecutivePromotionAdvisorPublicSmokeComparative(payload)" not in text:
        text = inject_before_pattern(
            text,
            r"^[ \t]*async function renderRuntimeExecutiveIndex\(\)",
            FUNCTION + "\n",
            "função de renderização",
        )
    if "renderExecutivePromotionAdvisorPublicSmokeComparative(payload);" not in text:
        pattern = r"^(?P<indent>[ \t]*)const cards = payload\.cards \|\| fallback\.cards;"
        match = re.search(pattern, text, flags=re.MULTILINE)
        if not match:
            raise RuntimeError("Hook do Runtime Executive Index não encontrado")
        hook = f"{match.group('indent')}renderExecutivePromotionAdvisorPublicSmokeComparative(payload);\n"
        text = text[: match.start()] + hook + text[match.start() :]
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Injeta comparativo público do Advisor no Ops Dashboard")
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--comparative-state", type=Path, required=True)
    args = parser.parse_args()
    source = hydrate_runtime_index(args.runtime_index, args.comparative_state)
    patch_dashboard(args.dashboard)
    print(json.dumps({"status": "patched", "source": source, "mode": "report-only"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
