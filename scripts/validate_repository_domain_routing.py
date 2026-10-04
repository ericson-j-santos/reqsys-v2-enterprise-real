#!/usr/bin/env python3
"""Valida o mapa machine-readable de domínios/repositórios e detecta drift do CI."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path("config/repository-domain-routing.json")


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("configuração raiz deve ser um objeto JSON")
    return payload


def active_workflows(root: Path) -> list[str]:
    workflow_dir = root / ".github" / "workflows"
    return sorted(
        path.name
        for path in workflow_dir.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )


def match_workflows(names: list[str], patterns: list[str]) -> list[str]:
    return sorted(
        name
        for name in names
        if any(fnmatch.fnmatch(name, pattern) for pattern in patterns)
    )


def validate_inventory(root: Path, payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    source_repository = str(payload.get("source_repository") or "")
    if not source_repository:
        errors.append("source_repository ausente")

    domains = payload.get("domains")
    if not isinstance(domains, list) or not domains:
        return errors + ["domains ausente ou vazio"], {}

    ids: set[str] = set()
    targets: set[str] = set()
    workflow_names = active_workflows(root)

    inventory = payload.get("workflow_inventory") or {}
    expected_total = inventory.get("baseline_count")
    if inventory.get("enforce_exact_count") is True and expected_total != len(workflow_names):
        errors.append(
            f"workflow inventory drift: expected={expected_total} actual={len(workflow_names)}"
        )

    summaries: dict[str, Any] = {}
    for domain in domains:
        if not isinstance(domain, dict):
            errors.append("domain inválido: esperado objeto")
            continue
        domain_id = str(domain.get("id") or "")
        target = str(domain.get("target_repository") or "")
        if not domain_id:
            errors.append("domain sem id")
            continue
        if domain_id in ids:
            errors.append(f"domain duplicado: {domain_id}")
        ids.add(domain_id)

        if not target:
            errors.append(f"{domain_id}: target_repository ausente")
        elif target in targets:
            errors.append(f"target_repository duplicado: {target}")
        targets.add(target)

        patterns = [str(item) for item in domain.get("workflow_globs") or []]
        matched = match_workflows(workflow_names, patterns)
        summaries[domain_id] = {
            "target_repository": target,
            "migration_state": domain.get("migration_state"),
            "matched_workflows": len(matched),
        }

        explicit_files = domain.get("workflow_files")
        if explicit_files is not None:
            expected_files = sorted(str(item) for item in explicit_files)
            if expected_files != matched:
                missing = sorted(set(expected_files) - set(matched))
                unexpected = sorted(set(matched) - set(expected_files))
                errors.append(
                    f"{domain_id}: workflow inventory mismatch "
                    f"missing={missing} unexpected={unexpected}"
                )

        expected_domain_count = domain.get("inventory_baseline_count")
        if expected_domain_count is not None and int(expected_domain_count) != len(matched):
            errors.append(
                f"{domain_id}: baseline count drift "
                f"expected={expected_domain_count} actual={len(matched)}"
            )

        state = str(domain.get("migration_state") or "")
        if domain_id != "core" and state != "retain" and target == source_repository:
            errors.append(f"{domain_id}: domínio extraível aponta para o source_repository")

    required_domains = {
        "core",
        "ci-platform",
        "bacen",
        "m365",
        "runtime-platform",
        "product-intelligence",
    }
    missing_domains = sorted(required_domains - ids)
    if missing_domains:
        errors.append(f"domínios obrigatórios ausentes: {missing_domains}")

    bacen = next((d for d in domains if isinstance(d, dict) and d.get("id") == "bacen"), {})
    if bacen.get("target_repository") != "ericson-j-santos/reqsys-governance-bacen":
        errors.append("bacen: target_repository canônico divergente")

    ci_platform = next(
        (d for d in domains if isinstance(d, dict) and d.get("id") == "ci-platform"),
        {},
    )
    if ci_platform.get("target_repository") != "ericson-j-santos/reqsys-ci-platform":
        errors.append("ci-platform: target_repository canônico divergente")

    summary = {
        "status": "passed" if not errors else "failed",
        "source_repository": source_repository,
        "workflow_count": len(workflow_names),
        "domains": summaries,
        "errors": errors,
    }
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida roteamento de domínios e inventário de workflows"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        payload = load_config(args.root / args.config)
        errors, summary = validate_inventory(args.root, payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif errors:
        for error in errors:
            print(f"ERRO: {error}", file=sys.stderr)
    else:
        print(
            "Repository domain routing validation passed "
            f"workflows={summary['workflow_count']}"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
