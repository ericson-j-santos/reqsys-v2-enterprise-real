#!/usr/bin/env python3
"""Validate ReqSys Application Balance Scorecard artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_PATH = ROOT / "docs/ops-dashboard/data/application-balance-scorecard-v0.1.0.json"
DOC_PATH = ROOT / "docs/ops-dashboard/application-balance-scorecard.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

EXPECTED_SCHEMA_VERSION = "0.1.0"
EXPECTED_ARTIFACT = "application-balance-scorecard"
EXPECTED_STATUSES = {"green", "yellow", "red"}
EXPECTED_DOMAIN_IDS = {
    "frontend_ux",
    "runtime_operacional",
    "backend_api_contracts",
    "ci_cd_quality_gates",
    "governanca_evidencias",
    "documentacao_rastreabilidade",
    "seguranca_lgpd",
}
REQUIRED_SUMMARY_FIELDS = {
    "weighted_green_percent",
    "weighted_yellow_percent",
    "weighted_red_percent",
    "balance_index_percent",
    "confidence",
    "primary_bottleneck",
    "recommended_pareto_path",
}
REQUIRED_DOC_TERMS = [
    "Application Balance Scorecard v0.1.0",
    "docs/ops-dashboard/data/application-balance-scorecard-v0.1.0.json",
    "Índice inicial de equilíbrio",
    "Caminho Pareto recomendado",
    "Guardrails",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"missing JSON artifact: {path.relative_to(ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("scorecard payload must be a JSON object")
    return payload


def validate_scorecard() -> None:
    payload = read_json(SCORECARD_PATH)

    if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        fail(f"schema_version must be {EXPECTED_SCHEMA_VERSION}")
    if payload.get("artifact") != EXPECTED_ARTIFACT:
        fail(f"artifact must be {EXPECTED_ARTIFACT}")

    status_model = payload.get("status_model")
    if not isinstance(status_model, dict):
        fail("status_model must be an object")
    missing_statuses = EXPECTED_STATUSES - set(status_model)
    if missing_statuses:
        fail(f"missing status_model entries: {sorted(missing_statuses)}")

    weights = payload.get("weights")
    if not isinstance(weights, dict):
        fail("weights must be an object")
    if sum(int(value) for value in weights.values()) != 100:
        fail("weights must sum 100")

    domains = payload.get("domains")
    if not isinstance(domains, list) or not domains:
        fail("domains must be a non-empty list")
    domain_ids = {item.get("id") for item in domains if isinstance(item, dict)}
    missing_domains = EXPECTED_DOMAIN_IDS - domain_ids
    if missing_domains:
        fail(f"missing expected domains: {sorted(missing_domains)}")

    weighted_total = 0
    for domain in domains:
        if not isinstance(domain, dict):
            fail(f"invalid domain entry: {domain!r}")
        for field in (
            "id",
            "name",
            "weight",
            "status",
            "current_signal",
            "target_state",
            "next_increment",
            "evidence_expected",
        ):
            if field not in domain:
                fail(f"domain {domain.get('id', '<unknown>')} missing field: {field}")
        if domain["status"] not in EXPECTED_STATUSES:
            fail(f"invalid status for domain {domain['id']}: {domain['status']}")
        if not isinstance(domain["evidence_expected"], list) or not domain["evidence_expected"]:
            fail(f"domain {domain['id']} must include evidence_expected entries")
        weighted_total += int(domain["weight"])

    if weighted_total != 100:
        fail("domain weights must sum 100")

    computed_summary = payload.get("computed_summary")
    if not isinstance(computed_summary, dict):
        fail("computed_summary must be an object")
    missing_summary = REQUIRED_SUMMARY_FIELDS - set(computed_summary)
    if missing_summary:
        fail(f"missing computed_summary fields: {sorted(missing_summary)}")
    if not 0 <= int(computed_summary["balance_index_percent"]) <= 100:
        fail("balance_index_percent must be between 0 and 100")

    guardrails = payload.get("guardrails")
    if not isinstance(guardrails, list) or len(guardrails) < 3:
        fail("guardrails must include at least three entries")


def validate_documentation() -> None:
    if not DOC_PATH.exists():
        fail(f"missing markdown documentation: {DOC_PATH.relative_to(ROOT)}")
    text = DOC_PATH.read_text(encoding="utf-8")
    for term in REQUIRED_DOC_TERMS:
        if term not in text:
            fail(f"missing term in scorecard documentation: {term}")

    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    if "Application Balance Scorecard v0.1.0" not in changelog:
        fail("CHANGELOG.md must reference Application Balance Scorecard v0.1.0")


def main() -> int:
    try:
        validate_scorecard()
        validate_documentation()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "validated": "application_balance_scorecard"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
