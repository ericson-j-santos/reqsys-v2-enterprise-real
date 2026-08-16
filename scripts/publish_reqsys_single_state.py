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


def _credential_control_plane_projection(
    credential_health: dict[str, Any] | None,
) -> dict[str, Any]:
    if not credential_health:
        return {
            "contract": "reqsys-credential-control-plane-health",
            "status": "EVIDENCE_NOT_PROVIDED",
            "security": {
                "stores_secret_values": False,
                "secret_values_exposed": False,
                "evidence_is_metadata_only": True,
            },
            "summary": {},
            "risks": [],
        }

    security = credential_health.get("security") or {}
    if security.get("secret_values_exposed") is True:
        raise ValueError(
            "credential health cannot be projected when secret values were exposed"
        )
    if security.get("stores_secret_values") is True:
        raise ValueError(
            "credential health cannot be projected when secret values were stored"
        )

    return {
        "contract": credential_health.get(
            "contract", "reqsys-credential-control-plane-health"
        ),
        "schema_version": credential_health.get("schema_version", "unknown"),
        "status": credential_health.get("status", "EVIDENCE_INCOMPLETE"),
        "generated_at_epoch": credential_health.get("generated_at_epoch"),
        "security": {
            "stores_secret_values": False,
            "secret_values_exposed": False,
            "evidence_is_metadata_only": True,
        },
        "summary": credential_health.get("summary", {}),
        "providers_cataloged": credential_health.get("providers_cataloged", []),
        "environments": credential_health.get("environments", {}),
        "risks": credential_health.get("risks", []),
    }


def build_contract(
    source: dict[str, Any],
    source_path: str,
    credential_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = source.get("decision", "EVIDENCE_INCOMPLETE")
    confidence = source.get("confidence", source.get("confidence_level", "unknown"))
    risks = source.get("risks", [])
    if not isinstance(risks, list):
        risks = [str(risks)]

    credential_projection = _credential_control_plane_projection(credential_health)
    combined_risks = list(risks)
    if credential_projection["status"] in {"DEGRADED", "EVIDENCE_INCOMPLETE"}:
        combined_risks.extend(
            f"credential_control_plane:{item}"
            for item in credential_projection.get("risks", [])
        )

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-single-state",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "official_source": {
            "path": source_path,
            "contract": source.get(
                "contract", "reqsys-unified-executive-integration-index"
            ),
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
            "credential_control_plane": credential_projection,
            "risks": combined_risks,
            "next_safe_increment": source.get(
                "next_safe_increment",
                "collect fresh runtime, deploy and smoke evidence before promotion",
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="docs/ops-dashboard/data/unified-executive-integration-index.json",
    )
    parser.add_argument(
        "--credential-health",
        default="",
        help="Optional sanitized Credential Control Plane health report",
    )
    parser.add_argument(
        "--output", default="docs/ops-dashboard/data/reqsys-single-state.json"
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)
    credential_health = (
        load_json(Path(args.credential_health)) if args.credential_health else None
    )
    contract = build_contract(
        load_json(source_path),
        args.source,
        credential_health=credential_health,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"published {output_path} status={contract['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
