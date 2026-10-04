"""Coerência entre a policy do merge governado e os gatilhos reais dos workflows.

A policy `governance/merge/current-sha-required-workflows.json` declara quais
workflows precisam estar registrados no SHA atual do PR. Um workflow obrigatório
que use filtro de `paths` no gatilho `pull_request` simplesmente não dispara em
PRs que não tocam esses caminhos: ele aparece como `missing` e bloqueia todo PR
do repositório. A tolerância `optional_when_not_registered` existe exatamente
para essa classe de workflow.

Os testes abaixo travam o invariante nos dois sentidos:

* todo workflow obrigatório com filtro de `paths` precisa ser tolerado quando
  ausente (evita o bloqueio sistêmico observado nas PRs de 2026-09-22);
* todo workflow tolerado precisa ter filtro de `paths` (evita que um gate que
  sempre dispara seja silenciosamente dispensado).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

POLICY_PATH = Path("governance/merge/current-sha-required-workflows.json")
WORKFLOWS_DIR = Path(".github/workflows")


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def workflow_files_by_name() -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for path in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"(?m)^name:[ \t]*(.+?)[ \t]*$", text)
        if not match:
            continue
        name = match.group(1).strip().strip("\"'")
        mapping.setdefault(name, path)
    return mapping


def pull_request_trigger_block(text: str) -> str | None:
    """Retorna o bloco `on.pull_request` do workflow, se existir."""
    on_block = re.search(r"(?ms)^on:\n(.*?)(?=^\S)", text)
    if not on_block:
        return None
    trigger = re.search(
        r"(?ms)^  pull_request:[ \t]*\n(.*?)(?=^  \S|\Z)", on_block.group(1)
    )
    if not trigger:
        return None
    return trigger.group(1)


def has_path_filter(block: str | None) -> bool:
    if not block:
        return False
    return bool(re.search(r"(?m)^ {4}paths(-ignore)?:", block))


def test_every_required_workflow_has_a_workflow_file() -> None:
    policy = load_policy()
    known = workflow_files_by_name()
    missing = [name for name in policy["required_workflows"] if name not in known]
    assert missing == [], f"workflows obrigatórios sem arquivo correspondente: {missing}"


def test_path_filtered_required_workflows_are_tolerated_when_absent() -> None:
    policy = load_policy()
    tolerated = set(policy["optional_when_not_registered"])
    known = workflow_files_by_name()

    blocking: list[str] = []
    for name in policy["required_workflows"]:
        path = known.get(name)
        if path is None:
            continue
        block = pull_request_trigger_block(path.read_text(encoding="utf-8"))
        if has_path_filter(block) and name not in tolerated:
            blocking.append(name)

    assert blocking == [], (
        "workflows obrigatórios com filtro de paths precisam constar em "
        f"optional_when_not_registered, senão bloqueiam todo PR: {blocking}"
    )


def test_tolerated_workflows_are_limited_to_path_filtered_ones() -> None:
    policy = load_policy()
    known = workflow_files_by_name()

    always_triggered: list[str] = []
    for name in policy["optional_when_not_registered"]:
        path = known.get(name)
        if path is None:
            continue
        block = pull_request_trigger_block(path.read_text(encoding="utf-8"))
        if block is not None and not has_path_filter(block):
            always_triggered.append(name)

    assert always_triggered == [], (
        "workflows sem filtro de paths sempre disparam e não podem ser "
        f"dispensados por ausência: {always_triggered}"
    )


def test_tolerance_is_a_subset_of_required_workflows() -> None:
    policy = load_policy()
    extra = set(policy["optional_when_not_registered"]) - set(
        policy["required_workflows"]
    )
    assert extra == set(), f"tolerância declarada fora de required_workflows: {extra}"
