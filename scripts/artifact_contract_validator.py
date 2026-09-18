#!/usr/bin/env python3
"""Report-only governance validator for operational JSON artifact contracts."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DOCS = ROOT / "docs"
CONTRACTS = DOCS / "contracts"
OUT = ROOT / "audit" / "artifact-contract-validation"
MINIMUM_FIELDS = [
    "generated_at",
    "source",
    "status",
    "confidence_level",
    "maturity_percent",
    "operational_risk",
    "commit_sha",
]
JSON_PATH_RE = re.compile(r"(?P<path>[A-Za-z0-9_./${}\\:-]+\.json)")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize(path: str) -> str:
    path = path.strip().strip('"\'')
    path = re.sub(r"\$\{\{[^}]+\}\}", "*", path)
    return path.replace("\\", "/")


def workflow_json_references() -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for wf in sorted(WORKFLOWS.glob("*.y*ml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        found = {normalize(m.group("path")) for m in JSON_PATH_RE.finditer(text)}
        refs[wf.relative_to(ROOT).as_posix()] = {p for p in found if not p.startswith("http")}
    return refs


def docs_json_files() -> list[str]:
    return [
        p.relative_to(ROOT).as_posix()
        for p in sorted(DOCS.rglob("*.json"))
        if "/contracts/" not in p.as_posix()
    ]


def schema_candidates(artifact: str) -> list[Path]:
    base = Path(artifact).name
    stem = base.removesuffix(".json")
    slug = stem.replace("_", "-")
    return [CONTRACTS / f"{stem}.schema.json", CONTRACTS / f"{slug}.schema.json"]


def schema_for(artifact: str) -> str | None:
    for candidate in schema_candidates(artifact):
        if candidate.exists():
            return candidate.relative_to(ROOT).as_posix()
    generic = CONTRACTS / "operational-json-artifact.schema.json"
    if generic.exists():
        return generic.relative_to(ROOT).as_posix()
    return None


def load_json_if_static(path: str) -> tuple[dict[str, Any] | None, str | None]:
    if "*" in path or "${{" in path:
        return None, "dynamic_path"
    p = ROOT / path
    if not p.exists():
        return None, "not_found_in_repository"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # report-only diagnostics, never fail the workflow for data divergence
        return None, f"invalid_json:{exc.__class__.__name__}"
    if not isinstance(data, dict):
        return None, "json_root_not_object"
    return data, None


def classify_source(path: str, workflows: list[str]) -> str:
    if workflows:
        return "workflow"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("artifacts/") or path.startswith("reports/"):
        return "repository_artifact"
    return "repository_json"


def main() -> int:
    workflow_refs = workflow_json_references()
    inventory: dict[str, dict[str, Any]] = {}

    for wf, refs in workflow_refs.items():
        for ref in refs:
            inventory.setdefault(ref, {"path": ref, "workflows": [], "declared_in_docs": False})["workflows"].append(wf)

    for doc_json in docs_json_files():
        entry = inventory.setdefault(doc_json, {"path": doc_json, "workflows": [], "declared_in_docs": True})
        entry["declared_in_docs"] = True

    items = []
    for artifact_path, entry in sorted(inventory.items()):
        data, load_status = load_json_if_static(artifact_path)
        applicable_fields = list(MINIMUM_FIELDS)
        if entry["workflows"] or os.getenv("GITHUB_RUN_ID"):
            applicable_fields.append("workflow_run_id")
        present = sorted([field for field in applicable_fields if data and field in data])
        missing = sorted([field for field in applicable_fields if data is not None and field not in data])
        items.append(
            {
                "artifact": artifact_path,
                "source": classify_source(artifact_path, entry["workflows"]),
                "workflows": sorted(entry["workflows"]),
                "declared_in_docs": entry["declared_in_docs"],
                "schema": schema_for(artifact_path),
                "load_status": load_status or "loaded",
                "minimum_fields_present": present,
                "minimum_fields_missing": missing,
                "status": "observed" if not missing else "divergence_report_only",
            }
        )

    missing_schema = [i for i in items if i["schema"] is None]
    divergences = [i for i in items if i["minimum_fields_missing"]]
    report = {
        "schema_version": "1.0.0",
        "generated_at": now(),
        "source": "scripts/artifact_contract_validator.py",
        "status": "report_only",
        "confidence_level": "medium",
        "maturity_percent": 35,
        "operational_risk": "medium",
        "commit_sha": os.getenv("GITHUB_SHA", "local"),
        "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "summary": {
            "artifacts_inventoried": len(items),
            "workflow_files_scanned": len(workflow_refs),
            "docs_json_files_scanned": len(docs_json_files()),
            "schemas_missing": len(missing_schema),
            "field_divergences": len(divergences),
        },
        "minimum_fields": MINIMUM_FIELDS + ["workflow_run_id when applicable"],
        "artifacts": items,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "artifact-contract-validation-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = [
        "# Artifact Contract Validation Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Status: `{report['status']}`",
        f"- Artifacts inventoried: `{len(items)}`",
        f"- Missing schemas: `{len(missing_schema)}`",
        f"- Field divergences: `{len(divergences)}`",
        "",
        "> Report-only: divergências não reprovam CI nesta versão inicial.",
        "",
        "## Inventory",
        "",
        "| Artifact | Source | Schema | Load | Missing minimum fields |",
        "|---|---|---|---|---|",
    ]
    for item in items:
        missing_text = ", ".join(item["minimum_fields_missing"]) or "-"
        schema = item["schema"] or "missing"
        md.append(f"| `{item['artifact']}` | {item['source']} | `{schema}` | {item['load_status']} | {missing_text} |")
    (OUT / "artifact-contract-validation-report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
