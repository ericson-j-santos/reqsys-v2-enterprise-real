#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

HIGH_CRITICALITY = {"high", "critical"}
ECOSYSTEM_ALIASES = {
    "microsoft": (
        "microsoft",
        "azure",
        "entra",
        "power automate",
        "dataverse",
        "sql server reporting services",
    ),
    "google": ("google", "gemini"),
    "github": ("github",),
    "groq": ("groq",),
    "figma": ("figma",),
    "redmine": ("redmine",),
    "postgresql": ("postgresql",),
    "redis": ("redis",),
}


def load_register(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registro de terceiros deve ser um objeto YAML")
    return payload


def ecosystem_for(provider_name: str, provider_id: str) -> str:
    normalized = provider_name.casefold()
    for ecosystem, aliases in ECOSYSTEM_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return ecosystem
    return f"independent:{provider_id}"


def build_report(register_path: Path) -> dict[str, Any]:
    register = load_register(register_path)
    providers = register.get("providers") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")

    provider_ids: set[str] = set()
    duplicate_provider_ids: list[str] = []
    structurally_invalid: list[str] = []
    ecosystems: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"provider_count": 0, "high_or_critical_count": 0, "provider_ids": []}
    )

    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            structurally_invalid.append(f"index:{index}")
            continue
        provider_id = str(provider.get("id") or "").strip()
        provider_name = str(provider.get("provider") or "").strip()
        criticality = str(provider.get("criticality") or "").lower()
        if not provider_id or not provider_name or not criticality:
            structurally_invalid.append(provider_id or f"index:{index}")
            continue
        if provider_id in provider_ids:
            duplicate_provider_ids.append(provider_id)
        provider_ids.add(provider_id)

        ecosystem = ecosystem_for(provider_name, provider_id)
        bucket = ecosystems[ecosystem]
        bucket["provider_count"] += 1
        bucket["provider_ids"].append(provider_id)
        if criticality in HIGH_CRITICALITY:
            bucket["high_or_critical_count"] += 1

    high_or_critical_total = sum(item["high_or_critical_count"] for item in ecosystems.values())
    normalized_ecosystems: dict[str, dict[str, Any]] = {}
    concentration_signals: list[str] = []
    for ecosystem, values in sorted(ecosystems.items()):
        high_share = (
            values["high_or_critical_count"] / high_or_critical_total
            if high_or_critical_total
            else 0.0
        )
        provider_share = values["provider_count"] / len(providers) if providers else 0.0
        normalized_ecosystems[ecosystem] = {
            **values,
            "provider_ids": sorted(values["provider_ids"]),
            "provider_share_percent": round(provider_share * 100, 2),
            "high_or_critical_share_percent": round(high_share * 100, 2),
        }
        if values["provider_count"] >= 3 or (
            high_or_critical_total >= 2 and high_share >= 0.4
        ):
            concentration_signals.append(ecosystem)

    structural_errors = bool(duplicate_provider_ids or structurally_invalid)
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "mapping_method": "deterministic_alias_rules_v1",
        "source_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "summary": {
            "provider_count": len(providers),
            "ecosystem_count": len(normalized_ecosystems),
            "high_or_critical_provider_count": high_or_critical_total,
            "concentration_signal_count": len(concentration_signals),
        },
        "ecosystems": normalized_ecosystems,
        "concentration_signal_ecosystems": sorted(concentration_signals),
        "duplicate_provider_ids": sorted(set(duplicate_provider_ids)),
        "structurally_invalid_provider_ids": sorted(structurally_invalid),
        "automatic_blocking": structural_errors,
        "risk_signal": "present" if concentration_signals else "none",
        "human_review_required": bool(concentration_signals),
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.register)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
