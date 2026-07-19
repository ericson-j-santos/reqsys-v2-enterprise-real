#!/usr/bin/env python3
"""Publish the canonical ReqSys Single State contract.

The contract promotes the unified executive integration index to the official
source consumed by governance, runtime and analytics without duplicating the
underlying evidence collectors.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONSUMERS = {
    "governance": {
        "purpose": "merge, approval and promotion decisions",
        "required_sections": ["decision", "governance", "risks"],
    },
    "runtime": {
        "purpose": "public runtime, deploy and smoke readiness",
        "required_sections": ["runtime", "production", "risks"],
    },
    "analytics": {
        "purpose": "throughput, lead time, CI stability and trend reporting",
        "required_sections": ["integration", "quality", "confidence"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_contract(source: dict[str, Any], source_path: str) -> dict[str, Any]:
    decision = source.get("decision", "EVIDENCE_INCOMPLETE")
    confidence = source.get("confidence", source.get("confidence_level", "unknown"))
    risks = source.get("risks", [])
    if not isinstance(risks, list):
        risks = [str(risks)]

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-single-state",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "official_source": {
            "path": source_path,
            "contract": source.get("contract", "reqsys-unified-executive-integration-index"),
            "schema_version": source.get("schema_version", "unknown"),
        },
        "status": decision,
        "confidence": confidence,
        "automatic_promotion_allowed": False,
        "human_approval_required": True,
        "consumers": CONSUMERS,
        "state": {
            "decision": decision,
            "integration": source.get("integration", {}),
            "quality": source.get("quality", {}),
            "governance": source.get("governance", {}),
            "runtime": source.get("runtime", {}),
            "production": source.get("production", {}),
            "risks": risks,
            "next_safe_increment": source.get(
                "next_safe_increment",
                "collect fresh runtime, deploy and smoke evidence before promotion",
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="docs/ops-dashboard/data/unified-executive-integration-index.json")
    parser.add_argument("--output", default="docs/ops-dashboard/data/reqsys-single-state.json")
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)
    contract = build_contract(load_json(source_path), args.source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"published {output_path} status={contract['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
