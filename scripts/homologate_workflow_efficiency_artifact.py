#!/usr/bin/env python3
"""Homologa o card Workflow Efficiency no artifact real do Ops Dashboard."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_HTML_TOKENS = (
    'id="workflow-efficiency-visual-card"',
    'function renderWorkflowEfficiency(payload)',
    'renderWorkflowEfficiency(payload);',
    'payload?.cards?.workflow_efficiency',
    'payload?.links?.workflow_efficiency',
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"contrato deve ser objeto JSON: {path}")
    return payload


def homologate(root: Path, correlation_id: str) -> dict[str, Any]:
    index_path = root / "index.html"
    runtime_index_path = root / "data" / "runtime-executive-index.json"

    errors: list[str] = []
    checks: dict[str, Any] = {}

    for name, path in (("index_html", index_path), ("runtime_executive_index", runtime_index_path)):
        exists = path.is_file()
        checks[f"{name}_exists"] = exists
        if not exists:
            errors.append(f"arquivo ausente: {path}")

    card: dict[str, Any] = {}
    link: Any = None

    if index_path.is_file():
        html = index_path.read_text(encoding="utf-8")
        missing_tokens = [token for token in REQUIRED_HTML_TOKENS if token not in html]
        checks["html_required_tokens"] = not missing_tokens
        checks["html_card_count"] = html.count('id="workflow-efficiency-visual-card"')
        if missing_tokens:
            errors.append(f"tokens HTML ausentes: {missing_tokens}")
        if checks["html_card_count"] != 1:
            errors.append("card visual deve existir exatamente uma vez")
        if "fetch('http" in html or 'fetch("http' in html:
            errors.append("artifact contém chamada fetch externa")
        checks["html_sha256"] = sha256_file(index_path)

    if runtime_index_path.is_file():
        try:
            payload = load_json(runtime_index_path)
            cards = payload.get("cards") or {}
            links = payload.get("links") or {}
            card = cards.get("workflow_efficiency") or {}
            link = links.get("workflow_efficiency")
            checks["contract_card_present"] = isinstance(card, dict) and bool(card)
            checks["contract_link_present"] = isinstance(link, str) and bool(link.strip())
            checks["contract_sha256"] = sha256_file(runtime_index_path)
            if not checks["contract_card_present"]:
                errors.append("cards.workflow_efficiency ausente ou vazio")
            if not checks["contract_link_present"]:
                errors.append("links.workflow_efficiency ausente ou vazio")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"contrato inválido: {exc}")

    status = "passed" if not errors else "failed"
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "status": status,
        "decision": "HOMOLOGATED" if status == "passed" else "BLOCKED",
        "source": "ops-dashboard-static",
        "root": str(root),
        "checks": checks,
        "workflow_efficiency": {
            "status": card.get("status") if isinstance(card, dict) else None,
            "score_percent": card.get("score_percent") if isinstance(card, dict) else None,
            "mode": card.get("mode") if isinstance(card, dict) else None,
            "link": link,
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Homologa Workflow Efficiency no artifact do Ops Dashboard")
    parser.add_argument("--root", type=Path, default=Path("artifacts/ops-dashboard"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/workflow-efficiency-artifact-homologation/evidence.json"),
    )
    parser.add_argument("--correlation-id", default="local")
    args = parser.parse_args()

    evidence = homologate(args.root, args.correlation_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
