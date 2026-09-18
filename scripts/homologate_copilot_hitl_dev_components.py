from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

SOLUTION_NAME = "ReqSysCopilotHITL"
REQUIRED_TOKENS = {
    "agents": [
        "ReqSys Supervisor",
        "ReqSys Requisitos",
        "ReqSys BDD",
        "ReqSys QA",
        "ReqSys Governança",
        "ReqSys DevOps",
    ],
    "tables": [
        "reqsys_workflow_instance",
        "reqsys_workflow_transition",
        "reqsys_approval_request",
        "reqsys_agent_execution",
        "reqsys_integration_outbox",
    ],
    "workflows": [
        "intake",
        "analista",
        "product owner",
        "gestor",
        "retomada",
        "dispatcher",
        "sla",
    ],
}


def _archive_text(package: Path) -> str:
    if not package.is_file():
        raise ValueError(f"Pacote exportado não encontrado: {package}")
    try:
        with zipfile.ZipFile(package) as archive:
            parts: list[str] = []
            for name in archive.namelist():
                if name.lower().endswith((".xml", ".json", ".yml", ".yaml", ".txt")):
                    parts.append(archive.read(name).decode("utf-8", errors="ignore"))
            return "\n".join(parts).lower()
    except zipfile.BadZipFile as exc:
        raise ValueError("Pacote exportado não é um ZIP válido") from exc


def homologate(solution_list: Path, exported_package: Path) -> dict[str, Any]:
    if not solution_list.is_file():
        raise ValueError(f"Lista de solutions não encontrada: {solution_list}")
    listed = solution_list.read_text(encoding="utf-8", errors="ignore")
    if SOLUTION_NAME.lower() not in listed.lower():
        raise ValueError(f"Solution {SOLUTION_NAME} não localizada no DEV")

    archive = _archive_text(exported_package)
    groups: dict[str, dict[str, Any]] = {}
    missing_total: list[str] = []
    for group, tokens in REQUIRED_TOKENS.items():
        missing = [token for token in tokens if token.lower() not in archive]
        groups[group] = {
            "expected": len(tokens),
            "found": len(tokens) - len(missing),
            "missing": missing,
        }
        missing_total.extend(f"{group}:{token}" for token in missing)

    status = "HOMOLOGATED" if not missing_total else "INCOMPLETE"
    evidence = {
        "solution": SOLUTION_NAME,
        "environment": "DEV",
        "status": status,
        "groups": groups,
        "missing_components": missing_total,
        "stg_prod_promotion_allowed": False,
        "human_approval_required": True,
    }
    if missing_total:
        raise ValueError("Componentes ausentes no export DEV: " + ", ".join(missing_total))
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution-list", type=Path, required=True)
    parser.add_argument("--exported-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = homologate(args.solution_list, args.exported_package)
    except ValueError as exc:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"status": "BLOCKED", "error": str(exc), "stg_prod_promotion_allowed": False}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise SystemExit(str(exc)) from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
