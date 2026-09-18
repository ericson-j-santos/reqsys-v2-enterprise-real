#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def enrich(index: dict[str, Any], indicator: dict[str, Any]) -> dict[str, Any]:
    if indicator.get("contract") != "reqsys-single-state-e2e-executive-indicator":
        raise ValueError("contrato E2E executivo inválido")
    if indicator.get("mode") != "advisory" or indicator.get("promotion_allowed") is not False:
        raise ValueError("guardrails E2E inválidos")
    if indicator.get("human_approval_required") is not True:
        raise ValueError("aprovação humana deve permanecer obrigatória")

    status = str(indicator.get("status") or "E2E_CORRELATION_PENDING")
    verified = status == "E2E_CORRELATION_VERIFIED"
    metrics = indicator.get("metrics") or {}

    result = dict(index)
    cards = dict(result.get("cards") or {})
    cards["e2e_correlation"] = {
        "available": True,
        "status": status.lower(),
        "verified": verified,
        "confidence_score": int(metrics.get("confidence_score") or 0) if verified else 0,
        "production_readiness_score": int(metrics.get("production_readiness_score") or 0) if verified else 0,
        "operational_risk": metrics.get("operational_risk") or ("low" if verified else "medium"),
        "promotion_allowed": False,
        "human_approval_required": True,
        "source_artifact": "reqsys-e2e-executive-indicator",
    }
    result["cards"] = cards

    summary = dict(result.get("summary") or {})
    summary["e2e_correlation_verified"] = verified
    summary["production_promotion_allowed"] = False
    summary["human_approval_required"] = True
    result["summary"] = summary
    result["schema_version"] = "1.2.0"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--indicator", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    indicator = json.loads(args.indicator.read_text(encoding="utf-8"))
    result = enrich(index, indicator)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
