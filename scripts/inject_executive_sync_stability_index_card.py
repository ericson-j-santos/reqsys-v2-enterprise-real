#!/usr/bin/env python3
"""Injeta o índice executivo de sincronização e estabilidade no Ops Dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CARD_ID = "executive-sync-stability-index-card"
HOOK = "<!-- REQSYS_EXECUTIVE_SYNC_STABILITY_INDEX -->"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(index: dict) -> dict:
    card = (index.get("cards") or {}).get("executive_sync_stability_index") or {}
    return {
        "status": card.get("status", "insufficient-environment-coverage"),
        "score": float(card.get("score", 0.0)),
        "environment_coverage": float(card.get("environment_coverage", 0.0)),
        "total_samples": int(card.get("total_samples", 0)),
        "weighted_pass_rate": float(card.get("weighted_pass_rate", 0.0)),
        "weighted_sync_rate": float(card.get("weighted_sync_rate", 0.0)),
        "minimum_stable_sequence": int(card.get("minimum_stable_sequence", 0)),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def render_card(card: dict) -> str:
    return f'''<section id="{CARD_ID}" data-reqsys-card="executive_sync_stability_index">
  <h2>Índice Executivo de Sincronização e Estabilidade</h2>
  <dl>
    <dt>Status</dt><dd>{card["status"]}</dd>
    <dt>Score</dt><dd>{card["score"]:.2f}</dd>
    <dt>Cobertura DEV/STG/PROD</dt><dd>{card["environment_coverage"]:.2f}%</dd>
    <dt>Amostras</dt><dd>{card["total_samples"]}</dd>
    <dt>Pass rate ponderado</dt><dd>{card["weighted_pass_rate"]:.2f}%</dd>
    <dt>Sync rate ponderado</dt><dd>{card["weighted_sync_rate"]:.2f}%</dd>
    <dt>Menor sequência estável</dt><dd>{card["minimum_stable_sequence"]}</dd>
  </dl>
  <p data-mode="report-only">Somente informativo; promoção exige aprovação humana.</p>
</section>'''


def inject(html: str, card_html: str) -> str:
    start = f'<section id="{CARD_ID}"'
    if start in html:
        before, rest = html.split(start, 1)
        _, after = rest.split("</section>", 1)
        return before + card_html + after
    if HOOK in html:
        return html.replace(HOOK, HOOK + "\n" + card_html, 1)
    if "</main>" in html:
        return html.replace("</main>", card_html + "\n</main>", 1)
    raise ValueError("hook canônico do Ops Dashboard não encontrado")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    args = parser.parse_args()

    index = load_json(args.runtime_index)
    card = normalize(index)
    index.setdefault("cards", {})["executive_sync_stability_index"] = card
    args.runtime_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    html = args.html.read_text(encoding="utf-8")
    args.html.write_text(inject(html, render_card(card)), encoding="utf-8")


if __name__ == "__main__":
    main()
