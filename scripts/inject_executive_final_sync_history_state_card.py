#!/usr/bin/env python3
"""Injeta o histórico final sincronizado no Ops Dashboard canônico."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

CARD_KEY = "executive_final_sync_history_state"
CARD_ID = "executive-final-sync-history-state"
HOOK = "<!-- REQSYS_EXECUTIVE_FINAL_SYNC_HISTORY_STATE -->"


def _safe_contract(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("cards", {}).get(CARD_KEY, {})
    if not isinstance(source, dict):
        source = {}
    environments = source.get("environments", {})
    return {
        "status": str(source.get("status", "insufficient-environment-coverage")),
        "coverage_complete": bool(source.get("coverage_complete", False)),
        "synchronized": bool(source.get("synchronized", False)),
        "total_samples": int(source.get("total_samples", 0) or 0),
        "weighted_pass_rate_percent": float(source.get("weighted_pass_rate_percent", 0.0) or 0.0),
        "minimum_stable_sequence": int(source.get("minimum_stable_sequence", 0) or 0),
        "common_fingerprint": str(source.get("common_fingerprint", "")),
        "eligible_for_human_review": bool(source.get("eligible_for_human_review", False)),
        "environments": environments if isinstance(environments, dict) else {},
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def _render(contract: dict[str, Any]) -> str:
    environments = ", ".join(sorted(contract["environments"].keys())) or "nenhum"
    fingerprint = contract["common_fingerprint"][:16] or "indisponível"
    return f'''<section id="{CARD_ID}" data-mode="report-only" data-production-blocker="false" data-human-approval-required="true">
  <h2>Histórico final de sincronização pública</h2>
  <dl>
    <dt>Status</dt><dd>{html.escape(contract["status"])}</dd>
    <dt>Cobertura DEV/STG/PROD</dt><dd>{"completa" if contract["coverage_complete"] else "incompleta"}</dd>
    <dt>Sincronização</dt><dd>{"sincronizado" if contract["synchronized"] else "com divergência"}</dd>
    <dt>Ambientes</dt><dd>{html.escape(environments)}</dd>
    <dt>Amostras</dt><dd>{contract["total_samples"]}</dd>
    <dt>Pass rate ponderado</dt><dd>{contract["weighted_pass_rate_percent"]:.2f}%</dd>
    <dt>Menor sequência estável</dt><dd>{contract["minimum_stable_sequence"]}</dd>
    <dt>Fingerprint comum</dt><dd>{html.escape(fingerprint)}</dd>
    <dt>Elegível para revisão humana</dt><dd>{"sim" if contract["eligible_for_human_review"] else "não"}</dd>
  </dl>
  <p>Indicador informativo. Nenhuma promoção automática é executada.</p>
</section>'''


def inject(index_html: str, runtime_index: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    contract = _safe_contract(runtime_index)
    runtime_index.setdefault("cards", {})[CARD_KEY] = contract
    card = _render(contract)
    marker = f'id="{CARD_ID}"'
    if marker in index_html:
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
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    args = parser.parse_args()
    runtime = json.loads(args.runtime_index.read_text(encoding="utf-8"))
    updated_html, updated_runtime = inject(args.html.read_text(encoding="utf-8"), runtime)
    args.html.write_text(updated_html, encoding="utf-8")
    args.runtime_index.write_text(json.dumps(updated_runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
