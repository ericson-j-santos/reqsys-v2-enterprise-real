#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

VAULT_NAME = "kv-reqsys-ccp"


def tool(name: str) -> str:
    for candidate in (name, f"{name}.cmd", f"{name}.exe", f"{name}.bat"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(f"tool_missing:{name}")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [tool("az"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=90,
        shell=False,
    )


def load_json(args: list[str]) -> Any:
    result = run([*args, "--output", "json"])
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None


def main() -> int:
    accounts = load_json(["account", "list"]) or []
    if not isinstance(accounts, list):
        accounts = []

    observations: list[dict[str, Any]] = []
    for account in accounts:
        if not isinstance(account, dict) or account.get("state") != "Enabled":
            continue
        sub_id = str(account.get("id") or "").strip()
        if not sub_id:
            continue
        probe = load_json([
            "keyvault", "show",
            "--name", VAULT_NAME,
            "--subscription", sub_id,
            "--query", "{id:id,name:name,location:location}",
        ])
        observations.append({
            "subscription_id": sub_id,
            "subscription_name": str(account.get("name") or ""),
            "tenant_id": str(account.get("tenantId") or ""),
            "is_default": bool(account.get("isDefault")),
            "vault_found": isinstance(probe, dict) and str(probe.get("name") or "") == VAULT_NAME,
            "vault_location": str(probe.get("location") or "") if isinstance(probe, dict) else "",
        })

    found = [item for item in observations if item["vault_found"]]
    result = {
        "status": "found" if len(found) == 1 else ("ambiguous" if len(found) > 1 else "not_found"),
        "vault_name": VAULT_NAME,
        "matches": found,
        "subscriptions_checked": len(observations),
        "secret_value_exposed": False,
        "rbac_changed": False,
        "production_touched": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if len(found) == 1 else 4


if __name__ == "__main__":
    raise SystemExit(main())
