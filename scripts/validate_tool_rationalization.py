#!/usr/bin/env python3
"""Valida o inventário governado de racionalização de ferramentas do ReqSys."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_DECISIONS = {"MANTER", "CONSOLIDAR", "DEPRECAR", "REMOVER"}
REQUIRED_ITEM_FIELDS = {
    "id",
    "path",
    "kind",
    "decision",
    "canonical",
    "target",
    "risk",
    "evidence",
    "blocking_dependencies",
    "exit_criteria",
    "next_action",
}
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("O inventário deve possuir um objeto JSON na raiz.")
    return payload


def validate_inventory_data(data: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or not SEMVER_PATTERN.match(schema_version):
        errors.append("schema_version deve seguir SemVer (x.y.z).")

    canonical_targets = data.get("canonical_targets")
    if not isinstance(canonical_targets, dict) or not canonical_targets:
        errors.append("canonical_targets deve ser um objeto não vazio.")
        canonical_targets = {}

    decisions = data.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        errors.append("decisions deve ser uma lista não vazia.")
        return errors

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    canonical_by_kind: dict[str, int] = {}

    for index, item in enumerate(decisions):
        prefix = f"decisions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} deve ser um objeto.")
            continue

        missing = sorted(REQUIRED_ITEM_FIELDS - set(item))
        if missing:
            errors.append(f"{prefix} sem campos obrigatórios: {', '.join(missing)}.")
            continue

        item_id = item["id"]
        item_path = item["path"]
        kind = item["kind"]
        decision = item["decision"]
        target = item["target"]
        canonical = item["canonical"]
        blockers = item["blocking_dependencies"]
        exit_criteria = item["exit_criteria"]

        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{prefix}.id deve ser texto não vazio.")
        elif item_id in seen_ids:
            errors.append(f"id duplicado: {item_id}.")
        else:
            seen_ids.add(item_id)

        if not isinstance(item_path, str) or not item_path.strip():
            errors.append(f"{prefix}.path deve ser texto não vazio.")
        elif item_path in seen_paths:
            errors.append(f"path duplicado: {item_path}.")
        else:
            seen_paths.add(item_path)
            if not (repo_root / item_path).exists():
                errors.append(f"path inexistente: {item_path}.")

        if decision not in ALLOWED_DECISIONS:
            errors.append(f"{prefix}.decision inválida: {decision!r}.")

        if not isinstance(target, str) or not target.strip():
            errors.append(f"{prefix}.target deve ser texto não vazio.")
        elif not (repo_root / target).exists():
            errors.append(f"target inexistente: {target}.")

        if not isinstance(blockers, list):
            errors.append(f"{prefix}.blocking_dependencies deve ser lista.")
            blockers = []

        if not isinstance(exit_criteria, list):
            errors.append(f"{prefix}.exit_criteria deve ser lista.")
            exit_criteria = []

        if decision in {"CONSOLIDAR", "DEPRECAR", "REMOVER"} and not exit_criteria:
            errors.append(f"{prefix} com decisão {decision} exige exit_criteria.")

        if decision == "REMOVER" and blockers:
            errors.append(
                f"{prefix} não pode ser REMOVER enquanto blocking_dependencies não estiver vazio."
            )

        if canonical is True:
            canonical_by_kind[kind] = canonical_by_kind.get(kind, 0) + 1
            if decision != "MANTER":
                errors.append(f"{prefix} canônico deve ter decisão MANTER.")
            expected_target = canonical_targets.get(kind)
            if expected_target and expected_target != item_path:
                errors.append(
                    f"{prefix} canônico de {kind} diverge de canonical_targets: "
                    f"{item_path} != {expected_target}."
                )

    for kind, target in canonical_targets.items():
        if not isinstance(target, str) or not target.strip():
            errors.append(f"canonical_targets.{kind} deve ser texto não vazio.")
            continue
        if not (repo_root / target).exists():
            errors.append(f"canonical_targets.{kind} aponta para path inexistente: {target}.")

    for kind, count in canonical_by_kind.items():
        if count > 1:
            errors.append(f"Mais de um item canônico definido para kind={kind}.")

    return errors


def validate_inventory_file(inventory_path: Path, repo_root: Path) -> list[str]:
    return validate_inventory_data(_load_json(inventory_path), repo_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        default="governance/tooling/rationalization-inventory.json",
        help="Caminho do inventário JSON.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Raiz do repositório usada para validar paths.",
    )
    args = parser.parse_args()

    inventory_path = Path(args.inventory).resolve()
    repo_root = Path(args.repo_root).resolve()

    try:
        errors = validate_inventory_file(inventory_path, repo_root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERRO: não foi possível validar o inventário: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("Inventário de racionalização inválido:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Inventário de racionalização válido (fail-closed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
