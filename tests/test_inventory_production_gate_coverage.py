from pathlib import Path

from scripts.inventory_production_gate_coverage import build_inventory


def write(root: Path, name: str, content: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(content, encoding="utf-8")


def test_inventory_detects_unprotected_production_workflow(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "deploy.yml",
        "jobs:\n  deploy:\n    environment: production\n    steps:\n      - run: flyctl deploy --app reqsys-api\n",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["production_capable_workflows"] == 1
    assert inventory["summary"]["unprotected_workflows"] == 1
    assert inventory["delivery_blocker"] is True
    assert inventory["automatic_enforcement_ready"] is False


def test_inventory_accepts_explicit_governed_gate_marker(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "deploy.yml",
        "# REQSYS_PRODUCTION_GOVERNANCE_GATE\njobs:\n  deploy:\n    environment: production\n",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["protected_workflows"] == 1
    assert inventory["summary"]["unprotected_workflows"] == 0
    assert inventory["automatic_enforcement_ready"] is True


def test_inventory_ignores_non_production_workflow(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(workflows, "lint.yml", "jobs:\n  lint:\n    steps:\n      - run: ruff check .\n")
    inventory = build_inventory(workflows)
    assert inventory["summary"]["production_capable_workflows"] == 0
    assert inventory["delivery_blocker"] is False
