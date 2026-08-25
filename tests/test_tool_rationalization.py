from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_tool_rationalization import validate_inventory_data


REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "governance" / "tooling" / "rationalization-inventory.json"


def _inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_inventory_atual_e_valido() -> None:
    errors = validate_inventory_data(_inventory(), REPO_ROOT)
    assert errors == []


def test_remove_e_bloqueado_enquanto_houver_dependencias() -> None:
    data = copy.deepcopy(_inventory())
    legado = next(item for item in data["decisions"] if item["id"] == "frontend-vuetify")
    legado["decision"] = "REMOVER"

    errors = validate_inventory_data(data, REPO_ROOT)

    assert any("não pode ser REMOVER" in error for error in errors)


def test_item_canonico_deve_ser_mantido() -> None:
    data = copy.deepcopy(_inventory())
    frontend = next(item for item in data["decisions"] if item["id"] == "frontend")
    frontend["decision"] = "CONSOLIDAR"
    frontend["exit_criteria"] = ["teste"]

    errors = validate_inventory_data(data, REPO_ROOT)

    assert any("canônico deve ter decisão MANTER" in error for error in errors)


def test_cada_categoria_declara_exatamente_um_canonico() -> None:
    data = copy.deepcopy(_inventory())
    data["decisions"] = [
        item for item in data["decisions"] if item["id"] != "docs-ops-dashboard"
    ]

    errors = validate_inventory_data(data, REPO_ROOT)

    assert any(
        "canonical_targets.operations_dashboard exige exatamente um item canônico" in error
        for error in errors
    )
