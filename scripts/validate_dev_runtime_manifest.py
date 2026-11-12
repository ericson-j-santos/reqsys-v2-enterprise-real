#!/usr/bin/env python3
"""Validação local e somente leitura do manifesto DEV (sem Fly.io/Docker/rede)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "public-access-urls.json"
DEV_URL = "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/"


def check_manifest(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["manifest_root_invalid"]
    discovery = payload.get("runtime_discovery")
    targets = payload.get("targets")
    if not isinstance(discovery, dict) or not isinstance(targets, list):
        return ["manifest_structure_invalid"]
    dev = discovery.get("dev")
    if not isinstance(dev, dict):
        return ["dev_runtime_missing"]

    errors: list[str] = []
    required = {
        "runtime_target": "pc24x7",
        "gateway": "http://127.0.0.1:8083",
        "public_transport": "cloudflare_quick_tunnel",
        "stable_url_target": DEV_URL,
        "stable_url_status": "signed_runtime_locator",
        "locator_channel": "ntfy_signed_ed25519",
        "cost_policy": "zero_additional_cost",
    }
    for key, expected in required.items():
        if dev.get(key) != expected:
            errors.append(f"dev_{key}_unexpected")

    for env in ("hml", "prod"):
        config = discovery.get(env)
        if not isinstance(config, dict) or config.get("runtime_target") != "not_promoted":
            errors.append(f"{env}_must_remain_not_promoted")

    dev_entries = [
        item for item in targets
        if isinstance(item, dict) and item.get("name") == "dev-stable-entrypoint"
        and item.get("environment") == "dev"
    ]
    if len(dev_entries) != 1:
        errors.append("dev_entrypoint_count_invalid")
    else:
        entry = dev_entries[0]
        if any((
            entry.get("url") != DEV_URL,
            entry.get("provider") != "github_pages",
            entry.get("type") != "locator",
            entry.get("required") is not True,
            entry.get("expectedStatus") != [200],
        )):
            errors.append("dev_entrypoint_contract_invalid")

    for item in targets:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            errors.append("invalid_target")
            continue
        parsed = urlparse(item["url"])
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or host.endswith((".fly.dev", ".fly.io")):
            errors.append("insecure_or_retired_provider_url")
        if item.get("environment") in ("hml", "prod") and item.get("lifecycle") != "not_promoted":
            errors.append("environment_promotion_not_allowed")
    return errors


def evaluate(path: Path = MANIFEST) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    errors = check_manifest(data)
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-pc24x7-static-dev-manifest",
        "status": "failed" if errors else "passed_with_warnings",
        "ok": not errors,
        "mode": "report_only",
        "summary": {
            "operational_status": "config_only" if not errors else "blocked",
            "physical_e2e_verified": False,
            "signed_locator_verified": False,
            "http_probe_performed": False,
            "manifest_version": data.get("schema_version") if isinstance(data, dict) else None,
            "manifest_updated_at": data.get("updated_at") if isinstance(data, dict) else None,
        },
        "issues": [
            *[{"severity": "error", "type": error} for error in errors],
            {"severity": "warning", "type": "physical_runtime_not_verified"},
        ],
    }


def main() -> int:
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
