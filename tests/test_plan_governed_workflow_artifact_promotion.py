from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.plan_governed_workflow_artifact_promotion import build_plan


def _write_artifacts(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    directory = tmp_path / "padrao"
    directory.mkdir()
    delivery = directory / "padrao-ouro-delivery-automation.yml"
    delivery.write_text(
        "# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"
        "jobs:\n"
        "  auto-open-pr:\n"
        "    runs-on: ubuntu-latest\n"
        "  production-gate:\n"
        "    uses: ./.github/workflows/bacen-production-hard-gate.yml\n"
        "  configure-prod-secrets:\n"
        "    if: needs.production-gate.outputs.production_allowed == 'true'\n"
        "  deploy-prod-a:\n"
        "    if: needs.production-gate.outputs.production_allowed == 'true'\n"
        "  deploy-prod-b:\n"
        "    if: needs.production-gate.outputs.production_allowed == 'true'\n"
        "  delivery-summary:\n"
        "    run: echo '| BACEN production gate |'\n",
        encoding="utf-8",
    )
    reusable = directory / "bacen-production-hard-gate.yml"
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
        "padrao_delivery": hashlib.sha256(delivery.read_bytes()).hexdigest(),
        "bacen_gate": hashlib.sha256(reusable.read_bytes()).hexdigest(),
    }
    return directory, digests


def test_builds_allowlisted_provider_neutral_plan(tmp_path: Path) -> None:
    padrao_dir, digests = _write_artifacts(tmp_path)
    plan = build_plan(padrao_dir, "a" * 40, digests, tmp_path / "generated-tests")
    assert plan["decision"] == "validated"
    assert plan["production_touched"] is False
    assert plan["force_push_allowed"] is False
    assert plan["direct_main_write_allowed"] is False
    assert len(plan["updates"]) == 3
    assert all(item["target"].startswith((".github/workflows/", "tests/")) for item in plan["updates"])
    assert not any("fly" in item["target"].lower() for item in plan["updates"])
    assert len(list((tmp_path / "generated-tests").glob("test_*_bacen_gate_contract.py"))) == 1


def test_rejects_digest_mismatch(tmp_path: Path) -> None:
    padrao_dir, digests = _write_artifacts(tmp_path)
    digests["padrao_delivery"] = "0" * 64
    with pytest.raises(ValueError, match="source_sha256_mismatch"):
        build_plan(padrao_dir, "a" * 40, digests, tmp_path / "tests")


def test_rejects_extra_artifact_file(tmp_path: Path) -> None:
    padrao_dir, digests = _write_artifacts(tmp_path)
    (padrao_dir / "unexpected.txt").write_text("not allowlisted", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_file_set_mismatch"):
        build_plan(padrao_dir, "a" * 40, digests, tmp_path / "tests")


def test_rejects_missing_governance_gate(tmp_path: Path) -> None:
    padrao_dir, digests = _write_artifacts(tmp_path)
    path = padrao_dir / "padrao-ouro-delivery-automation.yml"
    path.write_text("jobs:\n  deploy:\n", encoding="utf-8")
    digests["padrao_delivery"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="governance_marker_missing"):
        build_plan(padrao_dir, "a" * 40, digests, tmp_path / "tests")
