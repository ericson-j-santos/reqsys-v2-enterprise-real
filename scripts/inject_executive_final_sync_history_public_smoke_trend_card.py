#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

CARD_ID = "executive-final-sync-history-public-smoke-trend"


def build_card(state: dict) -> str:
    card = state.get("cards", {}).get("executive_final_sync_history_public_smoke_trend", {})
    status = card.get("status", "collecting-evidence")
    coverage = card.get("environment_coverage", "0/3")
    samples = card.get("samples", 0)
    pass_rate = card.get("pass_rate", 0)
    stable = card.get("minimum_stable_sequence", 0)
    eligible = bool(card.get("eligible_for_human_review", False))
    return f'''<section id="{CARD_ID}" data-mode="report-only" data-production-blocker="false">
  <h2>Tendência do smoke público final</h2>
  <dl>
    <dt>Status</dt><dd>{status}</dd>
    <dt>Cobertura</dt><dd>{coverage}</dd>
    <dt>Amostras</dt><dd>{samples}</dd>
    <dt>Pass rate</dt><dd>{pass_rate}%</dd>
    <dt>Sequência estável</dt><dd>{stable}</dd>
    <dt>Revisão humana</dt><dd>{str(eligible).lower()}</dd>
  </dl>
</section>'''


def inject(html: str, card: str) -> str:
    start = f'<section id="{CARD_ID}"'
    if start in html:
        prefix, rest = html.split(start, 1)
        _, suffix = rest.split("</section>", 1)
        return prefix + card + suffix
    marker = "</main>"
    return html.replace(marker, card + "\n" + marker) if marker in html else html + "\n" + card


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True)
    p.add_argument("--html", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    html = Path(args.html).read_text(encoding="utf-8")
    Path(args.output).write_text(inject(html, build_card(state)), encoding="utf-8")


if __name__ == "__main__":
    main()
