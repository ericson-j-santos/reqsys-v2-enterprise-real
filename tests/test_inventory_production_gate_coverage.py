from pathlib import Path

from scripts.inventory_production_gate_coverage import build_inventory


def write(root: Path, name: str, content: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(content, encoding="utf-8")


def test_inventory_detects_unprotected_confirmed_mutation(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "deploy.yml",
        "jobs:\n  deploy:\n    environment: production\n    steps:\n      - run: flyctl deploy --app reqsys-api\n",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["confirmed_mutation_workflows"] == 1
    assert inventory["summary"]["gate_required_workflows"] == 1
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


def test_inventory_classifies_prod_probe_as_observation_only(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "evidence.yml",
        "jobs:\n  evidence:\n    steps:\n      - run: python validate.py --environment prod\n",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["observation_only_workflows"] == 1
    assert inventory["summary"]["gate_required_workflows"] == 0
    assert inventory["delivery_blocker"] is False


def test_inventory_marks_deploy_without_explicit_prod_target_as_ambiguous(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(workflows, "deploy.yml", "jobs:\n  deploy:\n    steps:\n      - run: flyctl deploy\n")
    inventory = build_inventory(workflows)
    assert inventory["summary"]["ambiguous_mutation_workflows"] == 1
    assert inventory["summary"]["unprotected_workflows"] == 1


def test_inventory_ignores_non_production_workflow(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(workflows, "lint.yml", "jobs:\n  lint:\n    steps:\n      - run: ruff check .\n")
    inventory = build_inventory(workflows)
    assert inventory["summary"]["production_related_workflows"] == 0
    assert inventory["delivery_blocker"] is False
