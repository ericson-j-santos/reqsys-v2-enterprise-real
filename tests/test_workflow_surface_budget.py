from __future__ import annotations

import json
from pathlib import Path

from scripts.workflow_surface_budget import evaluate, workflow_name_and_broad_pr


def registry() -> dict:
    return {
        "canonical_pr_path": {
            "entry": "Pre-PR Readiness Gate",
            "blocking": ["CI Enterprise Fast"],
        }
    }


def write_workflow(root: Path, rel: str, *, name: str, trigger: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"name: {name}\non:\n{trigger}\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n", encoding="utf-8")


def test_blocks_net_workflow_growth(tmp_path: Path) -> None:
    rel = ".github/workflows/new.yml"
    write_workflow(tmp_path, rel, name="Optional New", trigger="  workflow_dispatch:")
    result = evaluate([("A", rel)], tmp_path, registry())
    assert result.status == "blocked"
    assert result.net_growth == 1


def test_allows_net_zero_replacement_when_new_workflow_is_scoped(tmp_path: Path) -> None:
    rel = ".github/workflows/new.yml"
    write_workflow(
        tmp_path,
        rel,
        name="Optional New",
        trigger="  pull_request:\n    paths:\n      - 'backend/**'",
    )
    result = evaluate([("D", ".github/workflows/old.yml"), ("A", rel)], tmp_path, registry())
    assert result.status == "passed"
    assert result.net_growth == 0


def test_blocks_new_broad_pull_request_outside_canonical_path(tmp_path: Path) -> None:
    rel = ".github/workflows/new.yml"
    write_workflow(tmp_path, rel, name="Optional New", trigger="  pull_request:")
    result = evaluate([("D", ".github/workflows/old.yml"), ("A", rel)], tmp_path, registry())
    assert result.status == "blocked"
    assert result.broad_pr_violations
    assert "fora do caminho canônico" in result.broad_pr_violations[0]


def test_allows_new_broad_pull_request_inside_canonical_path(tmp_path: Path) -> None:
    rel = ".github/workflows/new.yml"
    write_workflow(tmp_path, rel, name="CI Enterprise Fast", trigger="  pull_request:")
    result = evaluate([("D", ".github/workflows/old.yml"), ("A", rel)], tmp_path, registry())
    assert result.status == "passed"


def test_parser_distinguishes_scoped_and_broad_pull_request(tmp_path: Path) -> None:
    broad = tmp_path / "broad.yml"
    scoped = tmp_path / "scoped.yml"
    broad.write_text("name: Broad\non:\n  pull_request:\njobs: {}\n", encoding="utf-8")
    scoped.write_text("name: Scoped\non:\n  pull_request:\n    paths: ['backend/**']\njobs: {}\n", encoding="utf-8")
    assert workflow_name_and_broad_pr(broad) == ("Broad", True)
    assert workflow_name_and_broad_pr(scoped) == ("Scoped", False)


def test_repository_registry_declares_canonical_pr_path() -> None:
    payload = json.loads(Path("config/workflow-governance-registry.json").read_text(encoding="utf-8"))
    canonical = payload["canonical_pr_path"]
    assert canonical["entry"] == "Pre-PR Readiness Gate"
    assert "CI Enterprise Fast" in canonical["blocking"]
    assert "Governed Merge Queue" in canonical["blocking"]
