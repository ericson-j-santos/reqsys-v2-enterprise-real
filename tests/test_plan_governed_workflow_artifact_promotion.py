from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.plan_governed_workflow_artifact_promotion import build_plan


def _write_artifacts(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    homologation_dir = tmp_path / "homologation"
    padrao_dir = tmp_path / "padrao"
    homologation_dir.mkdir()
    padrao_dir.mkdir()

    homologation = homologation_dir / "fly-environment-homologation-gate.yml"
    homologation.write_text(
        "# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"
        "jobs:\n"
        "  production-gate:\n"
        "    if: ${{ inputs.environment == 'prod' && inputs.deploy == true }}\n"
        "    uses: ./.github/workflows/bacen-production-hard-gate.yml\n"
        "  deploy:\n"
        "    needs:\n"
        "      - production-gate\n"
        "    if: needs.production-gate.result == 'success' || needs.production-gate.result == 'skipped'\n",
        encoding="utf-8",
    )

    delivery = padrao_dir / "padrao-ouro-delivery-automation.yml"
    delivery.write_text(
        "# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"
        "jobs:\n"
        "  auto-open-pr:\n"
        "    runs-on: ubuntu-latest\n"
        "  production-gate:\n"
        "    uses: ./.github/workflows/bacen-production-hard-gate.yml\n"
        "  configure-prod-secrets:\n"
        "    if: needs.production-gate.outputs.production_allowed == 'true'\n"
        "  deploy-fly-prod:\n"
        "    if: needs.production-gate.outputs.production_allowed == 'true'\n"
        "  deploy-fly-frontend-prod:\n"
        "    if: needs.production-gate.outputs.production_allowed == 'true'\n"
        "  delivery-summary:\n"
        "    run: echo '| BACEN production gate |'\n",
        encoding="utf-8",
    )

    reusable = padrao_dir / "bacen-production-hard-gate.yml"
    reusable.write_text(
        "on:\n"
        "  workflow_call:\n"
        "    outputs:\n"
        "      production_allowed:\n"
        "        value: ${{ jobs.gate.outputs.production_allowed }}\n"
        "      decision:\n"
        "        value: ${{ jobs.gate.outputs.decision }}\n",
        encoding="utf-8",
    )

    digests = {
        "homologation": hashlib.sha256(homologation.read_bytes()).hexdigest(),
        "padrao_delivery": hashlib.sha256(delivery.read_bytes()).hexdigest(),
        "bacen_gate": hashlib.sha256(reusable.read_bytes()).hexdigest(),
    }
    return homologation_dir, padrao_dir, digests


def test_builds_validated_allowlisted_plan(tmp_path: Path) -> None:
    homologation_dir, padrao_dir, digests = _write_artifacts(tmp_path)
    tests_dir = tmp_path / "generated-tests"

    plan = build_plan(
        homologation_dir,
        padrao_dir,
        "a" * 40,
        digests,
        tests_dir,
    )

    assert plan["decision"] == "validated"
    assert plan["production_touched"] is False
    assert plan["force_push_allowed"] is False
    assert plan["direct_main_write_allowed"] is False
    assert len(plan["updates"]) == 5
    assert all(item["target"].startswith((".github/workflows/", "tests/")) for item in plan["updates"])
    assert len(list(tests_dir.glob("test_*_bacen_gate_contract.py"))) == 2


def test_rejects_digest_mismatch(tmp_path: Path) -> None:
    homologation_dir, padrao_dir, digests = _write_artifacts(tmp_path)
    digests["homologation"] = "0" * 64

    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        build_plan(homologation_dir, padrao_dir, "a" * 40, digests, tmp_path / "tests")


def test_rejects_extra_artifact_file(tmp_path: Path) -> None:
    homologation_dir, padrao_dir, digests = _write_artifacts(tmp_path)
    (homologation_dir / "unexpected.txt").write_text("not allowlisted", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact_file_set_mismatch"):
        build_plan(homologation_dir, padrao_dir, "a" * 40, digests, tmp_path / "tests")


def test_rejects_gate_after_productive_job(tmp_path: Path) -> None:
    homologation_dir, padrao_dir, digests = _write_artifacts(tmp_path)
    path = homologation_dir / "fly-environment-homologation-gate.yml"
    text = path.read_text(encoding="utf-8")
    before, gate = text.split("  production-gate:\n", 1)
    gate_body, deploy = gate.split("  deploy:\n", 1)
    path.write_text(before + "  deploy:\n" + deploy + "  production-gate:\n" + gate_body, encoding="utf-8")
    digests["homologation"] = hashlib.sha256(path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="gate_order_invalid"):
        build_plan(homologation_dir, padrao_dir, "a" * 40, digests, tmp_path / "tests")
