#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.development_prompt_coordinator import (  # noqa: E402
    PromptCatalogError,
    load_prompt_catalog,
)


def main() -> int:
    catalog_path = ROOT / "docs" / "prompts" / "catalog.json"
    try:
        catalog = load_prompt_catalog(catalog_path)
        missing_sources = [
            record["path"]
            for record in catalog["records"]
            if not (ROOT / record["path"]).is_file()
        ]
        if missing_sources:
            raise PromptCatalogError(
                "PDRs referenciados e não encontrados: " + ", ".join(sorted(missing_sources))
            )
    except PromptCatalogError as exc:
        print(f"::error title=Prompt catalog validation failed::{exc}")
        return 1

    summary = {
        "schema_version": catalog["schema_version"],
        "records": len(catalog["records"]),
        "active": sum(record["status"] == "active" for record in catalog["records"]),
        "domains": sorted({record["domain"] for record in catalog["records"]}),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Prompt catalog validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
