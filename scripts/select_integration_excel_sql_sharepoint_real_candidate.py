#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.integration_excel_sql_sharepoint_e2e import (  # noqa: E402
    download_workbook,
    graph_token,
    list_items,
    required_env,
    utcnow,
    workbook_candidates,
)

KNOWN_SYNTHETIC_FIXTURE_IDS = {"990000000000001"}
BUSINESS_KEY = "ChaveIntegracao"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def choose_real_candidate(
    candidates: Iterable[str],
    existing_items: Iterable[dict[str, Any]],
    *,
    forbidden_ids: set[str] | None = None,
) -> tuple[str, dict[str, int]]:
    forbidden = set(forbidden_ids or KNOWN_SYNTHETIC_FIXTURE_IDS)
    existing = {
        str((item.get("fields") or {}).get(BUSINESS_KEY) or "")
        for item in existing_items
    }
    stats = {
        "candidate_count": 0,
        "synthetic_rejected_count": 0,
        "sharepoint_residue_rejected_count": 0,
        "eligible_count": 0,
    }
    eligible: list[str] = []
    for raw in candidates:
        candidate = str(raw).strip()
        if not candidate:
            continue
        stats["candidate_count"] += 1
        if candidate in forbidden:
            stats["synthetic_rejected_count"] += 1
            continue
        if candidate in existing:
            stats["sharepoint_residue_rejected_count"] += 1
            continue
        eligible.append(candidate)
    stats["eligible_count"] = len(eligible)
    if not eligible:
        raise RuntimeError("nenhum_identificador_real_elegivel_no_excel")
    return eligible[0], stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seleciona identificador real já existente no Excel DEV sem criar dados sintéticos."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-env", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()

    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "excel_sql_sharepoint_functional_candidate",
        "captured_at": utcnow(),
        "environment": "dev",
        "source_sha": args.source_sha,
        "correlation_id": args.correlation_id,
        "status": "blocked",
        "candidate_source": "original_excel_workbook",
        "real_source": True,
        "mocked": False,
        "simulated": False,
        "synthetic_fixture_used": False,
        "selected_identifier_sha256": None,
        "workbook_sha256": None,
        "stats": {},
        "error": None,
    }

    try:
        drive_id = required_env("INTEGRATION_E2E_DRIVE_ID")
        file_id = required_env("INTEGRATION_E2E_FILE_ID")
        site_id = required_env("INTEGRATION_E2E_SITE_ID")
        list_id = required_env("INTEGRATION_E2E_LIST_ID")
        with httpx.Client(follow_redirects=True) as client:
            token = graph_token(client)
            workbook, _etag = download_workbook(client, token, drive_id, file_id)
            candidates = workbook_candidates(workbook)
            existing_items = list_items(client, token, site_id, list_id)
            selected, stats = choose_real_candidate(candidates, existing_items)

        evidence["status"] = "resolved"
        evidence["selected_identifier_sha256"] = digest(selected)
        evidence["workbook_sha256"] = hashlib.sha256(workbook).hexdigest()
        evidence["stats"] = stats
        args.github_env.parent.mkdir(parents=True, exist_ok=True)
        with args.github_env.open("a", encoding="utf-8") as handle:
            handle.write(f"INTEGRATION_E2E_SQL_FIXTURE_ID={selected}\n")
            handle.write("INTEGRATION_E2E_CANDIDATE_SOURCE=original_excel_workbook\n")
            handle.write(f"INTEGRATION_E2E_CANDIDATE_SHA256={digest(selected)}\n")
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - evidência sanitizada
        evidence["error"] = exc.__class__.__name__
        exit_code = 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "candidate_source": evidence["candidate_source"],
                "synthetic_fixture_used": evidence["synthetic_fixture_used"],
                "stats": evidence["stats"],
                "error": evidence["error"],
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
