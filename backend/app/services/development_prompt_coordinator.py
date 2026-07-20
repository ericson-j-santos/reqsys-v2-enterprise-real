from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.lowcode_adr_coordinator import planejar_coordenacao_por_adr

CATALOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "prompts" / "catalog.json"
PDR_ID_PATTERN = re.compile(r"^PDR-[A-Z0-9]+-\d{3}$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
ALLOWED_STATUS = {"draft", "active", "deprecated", "superseded"}
ALLOWED_RISK = {"low", "medium", "high", "critical"}


class PromptCatalogError(ValueError):
    """Erro de contrato do catálogo de prompts de desenvolvimento."""


def load_prompt_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or CATALOG_PATH
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PromptCatalogError(f"Catálogo PDR não encontrado: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise PromptCatalogError(f"Catálogo PDR contém JSON inválido: {exc}") from exc

    validate_prompt_catalog(payload)
    return payload


def validate_prompt_catalog(catalog: dict[str, Any]) -> None:
    if not SEMVER_PATTERN.fullmatch(str(catalog.get("schema_version", ""))):
        raise PromptCatalogError("schema_version deve usar SemVer.")

    defaults = catalog.get("defaults")
    records = catalog.get("records")
    if not isinstance(defaults, dict) or not isinstance(records, list) or not records:
        raise PromptCatalogError("defaults e records não vazios são obrigatórios.")

    identifiers: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise PromptCatalogError(f"records[{index}] deve ser um objeto.")

        required = {
            "id",
            "version",
            "status",
            "title",
            "domain",
            "task_types",
            "keywords",
            "path",
            "required_adrs",
            "agents",
            "required_evidence",
            "risk",
        }
        missing = sorted(required.difference(record))
        if missing:
            raise PromptCatalogError(f"{record.get('id', index)} sem campos: {', '.join(missing)}")

        record_id = str(record["id"])
        if not PDR_ID_PATTERN.fullmatch(record_id):
            raise PromptCatalogError(f"Identificador PDR inválido: {record_id}")
        if record_id in identifiers:
            raise PromptCatalogError(f"Identificador PDR duplicado: {record_id}")
        identifiers.add(record_id)

        if not SEMVER_PATTERN.fullmatch(str(record["version"])):
            raise PromptCatalogError(f"Versão inválida em {record_id}")
        if record["status"] not in ALLOWED_STATUS:
            raise PromptCatalogError(f"Status inválido em {record_id}")
        if record["risk"] not in ALLOWED_RISK:
            raise PromptCatalogError(f"Risco inválido em {record_id}")

        for field in ("task_types", "keywords", "required_adrs", "agents", "required_evidence"):
            value = record[field]
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
                raise PromptCatalogError(f"{field} deve ser uma lista de textos não vazia em {record_id}")

        if "ADR-045" not in record["required_adrs"]:
            raise PromptCatalogError(f"{record_id} deve referenciar ADR-045")


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def resolve_prompt_records(
    objective: str,
    *,
    pdr_refs: list[str] | None = None,
    catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    active_catalog = catalog or load_prompt_catalog()
    explicit = {item.strip().upper() for item in (pdr_refs or []) if item.strip()}
    normalized_objective = _normalize(objective)

    selected: list[dict[str, Any]] = []
    for record in active_catalog["records"]:
        if record["status"] != "active":
            continue
        keyword_match = any(_normalize(keyword) in normalized_objective for keyword in record["keywords"])
        if record["id"] in explicit or keyword_match:
            selected.append(record)

    if not selected:
        selected = [record for record in active_catalog["records"] if record["id"] == "PDR-DEV-001"]

    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(selected, key=lambda record: (risk_order[record["risk"]], record["id"]))


def plan_development_coordination(
    *,
    objective: str,
    adr_refs: list[str] | None = None,
    pdr_refs: list[str] | None = None,
    dry_run: bool = True,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    pdrs = resolve_prompt_records(objective, pdr_refs=pdr_refs)
    resolved_adrs = sorted({adr for record in pdrs for adr in record["required_adrs"]}.union(adr_refs or []))
    adr_plan = planejar_coordenacao_por_adr(
        objetivo=objective,
        adr_refs=resolved_adrs,
        dry_run=dry_run,
        correlation_id=correlation_id,
    )

    return {
        **adr_plan,
        "schema_version": "1.0.0",
        "capability": "ReqSys ADR + PDR Development Coordinator",
        "prompt_catalog": "docs/prompts/catalog.json",
        "pdrs": [
            {
                "id": record["id"],
                "version": record["version"],
                "title": record["title"],
                "domain": record["domain"],
                "risk": record["risk"],
                "agents": record["agents"],
                "required_adrs": record["required_adrs"],
                "required_evidence": record["required_evidence"],
                "source": record["path"],
            }
            for record in pdrs
        ],
        "evidence_manifest": sorted({evidence for record in pdrs for evidence in record["required_evidence"]}),
        "human_approval_required": any(record["risk"] in {"high", "critical"} for record in pdrs),
    }
