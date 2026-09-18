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


def test_inventory_accepts_structural_prod_proposal_gate(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "backup-rollout.yml",
        """jobs:
  evaluate-stg:
    outputs:
      prod_allowed: ${{ steps.result.outputs.prod_allowed }}
  propose-prod:
    needs: evaluate-stg
    if: >-
      github.event_name == 'workflow_dispatch' &&
      needs.evaluate-stg.outputs.prod_allowed == 'true' &&
      inputs.approve_prod == 'APROVO-PROD'
    environment: production
    steps:
      - run: echo prod_rollout_candidate_requires_approval
      - run: gh pr create --base main --head automation/prod
""",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["protected_workflows"] == 1
    assert inventory["summary"]["unprotected_workflows"] == 0
    assert inventory["delivery_blocker"] is False
    assert inventory["automatic_enforcement_ready"] is True


def test_inventory_rejects_incomplete_structural_prod_gate(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "unsafe-rollout.yml",
        """jobs:
  propose-prod:
    environment: production
    steps:
      - run: echo prod_rollout_candidate_requires_approval
      - run: gh pr create --base main --head automation/prod
""",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["unprotected_workflows"] == 1
    assert inventory["delivery_blocker"] is True


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


def test_inventory_marks_deploy_without_explicit_target_as_ambiguous(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(workflows, "deploy.yml", "jobs:\n  deploy:\n    steps:\n      - run: flyctl deploy\n")
    inventory = build_inventory(workflows)
    assert inventory["summary"]["ambiguous_mutation_workflows"] == 1
    assert inventory["summary"]["unprotected_workflows"] == 1


def test_inventory_excludes_explicit_staging_deploy_from_prod_gate(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "staging.yml",
        "jobs:\n  deploy:\n    environment: staging\n    steps:\n      - run: flyctl deploy --config fly.staging.toml --app reqsys-api-stg\n",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["nonproduction_mutation_workflows"] == 1
    assert inventory["summary"]["gate_required_workflows"] == 0
    assert inventory["summary"]["unprotected_workflows"] == 0
    assert inventory["delivery_blocker"] is False


def test_prod_app_pattern_does_not_match_staging_suffix(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(
        workflows,
        "staging.yml",
        "jobs:\n  deploy:\n    steps:\n      - run: flyctl deploy --app reqsys-app-stg\n",
    )
    inventory = build_inventory(workflows)
    assert inventory["summary"]["confirmed_mutation_workflows"] == 0
    assert inventory["summary"]["nonproduction_mutation_workflows"] == 1


def test_inventory_ignores_non_mutating_non_production_workflow(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    write(workflows, "lint.yml", "jobs:\n  lint:\n    steps:\n      - run: ruff check .\n")
    inventory = build_inventory(workflows)
    assert inventory["summary"]["production_related_workflows"] == 0
    assert inventory["delivery_blocker"] is False


def test_repository_has_no_unprotected_production_mutation_paths():
    workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    inventory = build_inventory(workflows)
    unprotected = [item["path"] for item in inventory["unprotected_workflows"]]
    assert unprotected == [], (
        "Caminhos de mutação em produção sem proteção governada: "
        + ", ".join(unprotected)
    )
    assert inventory["delivery_blocker"] is False
    assert inventory["automatic_enforcement_ready"] is True
