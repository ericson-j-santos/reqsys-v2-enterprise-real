#!/usr/bin/env python3
"""Inject the comparative public smoke trend card into the canonical Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

CARD_KEY = "executive_promotion_advisor_comparative_public_smoke_trend"
HOOK = "<!-- REQSYS_EXECUTIVE_PROMOTION_ADVISOR_COMPARATIVE_SMOKE_TREND -->"


def _safe_card(source: dict[str, Any]) -> dict[str, Any]:
    card = deepcopy(source.get("cards", {}).get(CARD_KEY, {}))
    card.update({
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    })
    card.setdefault("status", "REVIEW")
    card.setdefault("trend", "insufficient-environment-coverage")
    card.setdefault("summary", {})
    card["summary"].setdefault("environment_count", 0)
    card["summary"].setdefault("sample_count", 0)
    card["summary"].setdefault("weighted_pass_rate_percent", 0.0)
    card["summary"].setdefault("minimum_visual_consistency_percent", 0.0)
    card["summary"].setdefault("minimum_stable_streak", 0)
    return card


def _render(card: dict[str, Any]) -> str:
    s = card["summary"]
    return (
        f'{HOOK}\n<section id="{CARD_KEY}" data-mode="report-only" '
        'data-production-blocker="false" data-human-approval-required="true">'
        '<h2>Advisor — tendência do smoke comparativo</h2>'
        f'<p>Status: <strong>{card.get("status")}</strong></p>'
        f'<p>Tendência: <strong>{card.get("trend")}</strong></p>'
        f'<p>Ambientes: {s.get("environment_count")}/3 · Amostras: {s.get("sample_count")}</p>'
        f'<p>Taxa ponderada: {s.get("weighted_pass_rate_percent")}% · '
        f'Consistência visual mínima: {s.get("minimum_visual_consistency_percent")}% · '
        f'Sequência estável mínima: {s.get("minimum_stable_streak")}</p>'
        '<p>Decisão exclusivamente humana.</p></section>\n'
    )


def inject(html: str, runtime_index: dict[str, Any], trend_state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    card = _safe_card(trend_state)
    output = deepcopy(runtime_index)
    output.setdefault("cards", {})[CARD_KEY] = card
    block = _render(card)
    if HOOK in html:
        start = html.index(HOOK)
        end = html.find("</section>", start)
        if end == -1:
            raise ValueError("card hook found without closing section")
        html = html[:start] + block + html[end + len("</section>"):]
    elif "</main>" in html:
        html = html.replace("</main>", block + "</main>", 1)
    else:
        html += block
    return html, output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--runtime-index", required=True)
    parser.add_argument("--trend-state", required=True)
    args = parser.parse_args()
    html_path = Path(args.html)
    index_path = Path(args.runtime_index)
    trend_path = Path(args.trend_state)
    html, index = inject(
        html_path.read_text(encoding="utf-8"),
        json.loads(index_path.read_text(encoding="utf-8")),
        json.loads(trend_path.read_text(encoding="utf-8")),
    )
    html_path.write_text(html, encoding="utf-8")
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
