#!/usr/bin/env python3
"""Inject the Executive Sync Stability Index into the canonical Ops Dashboard."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

CARD_ID = "executive-sync-stability-index"
HOOK = "<!-- REQSYS_EXECUTIVE_SYNC_STABILITY_INDEX -->"


def _safe_contract(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("cards", {}).get("executive_sync_stability_index", {})
    return {
        "status": str(source.get("status", "insufficient-environment-coverage")),
        "score": float(source.get("score", 0.0) or 0.0),
        "environment_coverage": float(source.get("environment_coverage", 0.0) or 0.0),
        "total_samples": int(source.get("total_samples", 0) or 0),
        "weighted_pass_rate": float(source.get("weighted_pass_rate", 0.0) or 0.0),
        "weighted_sync_rate": float(source.get("weighted_sync_rate", 0.0) or 0.0),
        "minimum_stable_sequence": int(source.get("minimum_stable_sequence", 0) or 0),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def _render(contract: dict[str, Any]) -> str:
    return f'''<section id="{CARD_ID}" data-mode="report-only" data-production-blocker="false" data-human-approval-required="true">
  <h2>Índice executivo de sincronização e estabilidade</h2>
  <dl>
    <dt>Estado</dt><dd>{html.escape(contract["status"])}</dd>
    <dt>Score</dt><dd>{contract["score"]:.2f}</dd>
    <dt>Cobertura DEV/STG/PROD</dt><dd>{contract["environment_coverage"]:.2f}%</dd>
    <dt>Amostras</dt><dd>{contract["total_samples"]}</dd>
    <dt>Pass rate ponderado</dt><dd>{contract["weighted_pass_rate"]:.2f}%</dd>
    <dt>Sync rate ponderado</dt><dd>{contract["weighted_sync_rate"]:.2f}%</dd>
    <dt>Menor sequência estável</dt><dd>{contract["minimum_stable_sequence"]}</dd>
  </dl>
  <p>Elegibilidade indica somente revisão humana. Nenhuma promoção automática é executada.</p>
</section>'''


def inject(index_html: str, runtime_index: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    contract = _safe_contract(runtime_index)
    runtime_index.setdefault("cards", {})["executive_sync_stability_index"] = contract
    card = _render(contract)

    if f'id="{CARD_ID}"' in index_html:
        start = index_html.index(f'<section id="{CARD_ID}"')
        end = index_html.index("</section>", start) + len("</section>")
        updated_html = index_html[:start] + card + index_html[end:]
    elif HOOK in index_html:
        updated_html = index_html.replace(HOOK, f"{HOOK}\n{card}", 1)
    elif "</main>" in index_html:
        updated_html = index_html.replace("</main>", f"{card}\n</main>", 1)
    else:
        updated_html = index_html + "\n" + card

    return updated_html, runtime_index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--runtime-index", required=True)
    args = parser.parse_args()

    html_path = Path(args.html)
    runtime_path = Path(args.runtime_index)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    updated_html, updated_runtime = inject(html_path.read_text(encoding="utf-8"), runtime)
    html_path.write_text(updated_html, encoding="utf-8")
    runtime_path.write_text(json.dumps(updated_runtime, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
