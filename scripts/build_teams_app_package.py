#!/usr/bin/env python3
"""Gera o pacote Teams DEV com RSC mínimo e validações fail-closed."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
import zipfile
from pathlib import Path

RSC_EXPECTED = [{"name": "ChannelMessage.Read.Group", "type": "Application"}]
EXTRA_DOMAINS = ("reqsys-api-dev.fly.dev", "token.botframework.com")


def _validate_manifest(manifest: dict) -> None:
    bots = manifest.get("bots") or []
    if len(bots) != 1:
        raise ValueError("teams_manifest_bot_count_invalid")
    scopes = set(bots[0].get("scopes") or [])
    if not {"personal", "team"}.issubset(scopes):
        raise ValueError("teams_manifest_team_scope_required")

    rsc = (
        manifest.get("authorization", {})
        .get("permissions", {})
        .get("resourceSpecific", [])
    )
    if rsc != RSC_EXPECTED:
        raise ValueError("teams_manifest_rsc_not_least_privilege")
    web_app = manifest.get("webApplicationInfo") or {}
    if not web_app.get("resource"):
        raise ValueError("teams_manifest_rsc_resource_required")


def build_package(source_dir: Path, output_dir: Path, output_zip: Path, app_id: str) -> None:
    uuid.UUID(app_id)
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest(manifest)

    manifest["id"] = app_id
    manifest["bots"][0]["botId"] = app_id
    manifest["webApplicationInfo"]["id"] = app_id
    domains = list(manifest.get("validDomains") or [])
    for domain in EXTRA_DOMAINS:
        if domain not in domains:
            domains.append(domain)
    manifest["validDomains"] = domains

    output_dir.mkdir(parents=True, exist_ok=True)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for icon in ("color.png", "outline.png"):
        shutil.copy2(source_dir / icon, output_dir / icon)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as package:
        for name in ("manifest.json", "color.png", "outline.png"):
            package.write(output_dir / name, arcname=name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-zip", type=Path, required=True)
    parser.add_argument("--app-id", required=True)
    args = parser.parse_args()

    try:
        build_package(args.source_dir, args.output_dir, args.output_zip, args.app_id)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"TEAMS_PACKAGE_FAILED: {exc}")
        return 2

    print(f"TEAMS_PACKAGE_OK: {args.output_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
