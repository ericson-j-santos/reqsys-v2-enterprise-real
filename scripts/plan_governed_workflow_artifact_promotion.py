#!/usr/bin/env python3
"""Validate generated production-workflow artifacts before governed promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")

HOMOLOGATION_FILE = "fly-environment-homologation-gate.yml"
PADRAO_DELIVERY_FILE = "padrao-ouro-delivery-automation.yml"
BACEN_GATE_FILE = "bacen-production-hard-gate.yml"

ALLOWLIST = {
    "homologation": {
        HOMOLOGATION_FILE: ".github/workflows/fly-environment-homologation-gate.yml",
    },
    "padrao_ouro": {
        PADRAO_DELIVERY_FILE: ".github/workflows/padrao-ouro-delivery-automation.yml",
        BACEN_GATE_FILE: ".github/workflows/bacen-production-hard-gate.yml",
    },
}

HOMOLOGATION_TEST = '''from pathlib import Path

WORKFLOW = Path(".github/workflows/fly-environment-homologation-gate.yml")


def test_bacen_gate_precedes_production_environment_and_secret() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = text.index("\\n  production-gate:\\n")
    deploy = text.index("\\n  deploy:\\n")
    environment = text.index("    environment:\\n", deploy)
    secret = text.index("FLY_API_TOKEN:", deploy)

    assert text.startswith("# REQSYS_PRODUCTION_GOVERNANCE_GATE\\n")
    assert gate < deploy < environment < secret
    assert "inputs.environment == 'prod' && inputs.deploy == true" in text
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in text
    assert "      - production-gate" in text
    assert "needs.production-gate.result == 'success' || needs.production-gate.result == 'skipped'" in text
    assert "APROVO-PROD" in text
    assert "          - dev" in text and "          - stg" in text and "          - prod" in text
'''

PADRAO_TEST = '''from pathlib import Path

DELIVERY = Path(".github/workflows/padrao-ouro-delivery-automation.yml")
REUSABLE = Path(".github/workflows/bacen-production-hard-gate.yml")


def test_productive_jobs_require_bacen_authorization() -> None:
    delivery = DELIVERY.read_text(encoding="utf-8")
    reusable = REUSABLE.read_text(encoding="utf-8")
    gate = delivery.index("\\n  production-gate:\\n")
    secrets_job = delivery.index("\\n  configure-prod-secrets:\\n")

    assert delivery.startswith("# REQSYS_PRODUCTION_GOVERNANCE_GATE\\n")
    assert gate < secrets_job
    assert "uses: ./.github/workflows/bacen-production-hard-gate.yml" in delivery
    assert delivery.count("needs.production-gate.outputs.production_allowed == 'true'") >= 3
    assert "| BACEN production gate |" in delivery
    assert "  auto-open-pr:" in delivery
    assert "production_allowed:" in reusable
    assert "decision:" in reusable
    assert "value: ${{ jobs.gate.outputs.production_allowed }}" in reusable
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_digest(value: str, label: str) -> str:
    digest = value.strip().lower()
    if not HEX_64.fullmatch(digest):
        raise ValueError(f"{label}: invalid_sha256")
    return digest


def require_base_sha(value: str) -> str:
    sha = value.strip().lower()
    if not HEX_40.fullmatch(sha):
        raise ValueError("expected_base_sha: invalid_commit_sha")
    return sha


def exact_files(directory: Path, expected: set[str], label: str) -> dict[str, Path]:
    if not directory.is_dir():
        raise ValueError(f"{label}: directory_missing")
    observed = {
        path.relative_to(directory).as_posix(): path
        for path in directory.rglob("*")
        if path.is_file()
    }
    if set(observed) != expected:
        raise ValueError(f"{label}: artifact_file_set_mismatch")
    return observed


def validate_markers(homologation: str, delivery: str, reusable: str) -> None:
    if not homologation.startswith("# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"):
        raise ValueError("homologation: governance_marker_missing")
    h_gate = homologation.find("\n  production-gate:\n")
    h_deploy = homologation.find("\n  deploy:\n")
    if h_gate < 0 or h_deploy < 0 or h_gate >= h_deploy:
        raise ValueError("homologation: gate_order_invalid")
    for marker in (
        "inputs.environment == 'prod' && inputs.deploy == true",
        "uses: ./.github/workflows/bacen-production-hard-gate.yml",
        "needs.production-gate.result == 'success' || needs.production-gate.result == 'skipped'",
    ):
        if marker not in homologation:
            raise ValueError("homologation: contract_marker_missing")

    if not delivery.startswith("# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"):
        raise ValueError("padrao_ouro: governance_marker_missing")
    p_gate = delivery.find("\n  production-gate:\n")
    p_secrets = delivery.find("\n  configure-prod-secrets:\n")
    if p_gate < 0 or p_secrets < 0 or p_gate >= p_secrets:
        raise ValueError("padrao_ouro: gate_order_invalid")
    if delivery.count("needs.production-gate.outputs.production_allowed == 'true'") < 3:
        raise ValueError("padrao_ouro: productive_authorization_missing")
    if "| BACEN production gate |" not in delivery:
        raise ValueError("padrao_ouro: summary_marker_missing")
    for marker in (
        "production_allowed:",
        "decision:",
        "value: ${{ jobs.gate.outputs.production_allowed }}",
    ):
        if marker not in reusable:
            raise ValueError("reusable_gate: workflow_call_output_missing")


def write_tests(directory: Path) -> list[dict[str, str]]:
    directory.mkdir(parents=True, exist_ok=True)
    tests = {
        "test_fly_environment_homologation_bacen_gate_contract.py": HOMOLOGATION_TEST,
        "test_padrao_ouro_delivery_bacen_gate_contract.py": PADRAO_TEST,
    }
    result: list[dict[str, str]] = []
    for name, content in tests.items():
        path = directory / name
        path.write_text(content, encoding="utf-8")
        result.append(
            {
                "source": str(path),
                "target": f"tests/{name}",
                "sha256": sha256(path),
            }
        )
    return result


def build_plan(
    homologation_dir: Path,
    padrao_dir: Path,
    expected_base_sha: str,
    expected_digests: dict[str, str],
    tests_dir: Path,
) -> dict[str, Any]:
    base_sha = require_base_sha(expected_base_sha)
    h_files = exact_files(homologation_dir, set(ALLOWLIST["homologation"]), "homologation")
    p_files = exact_files(padrao_dir, set(ALLOWLIST["padrao_ouro"]), "padrao_ouro")

    actual = {
        "homologation": sha256(h_files[HOMOLOGATION_FILE]),
        "padrao_delivery": sha256(p_files[PADRAO_DELIVERY_FILE]),
        "bacen_gate": sha256(p_files[BACEN_GATE_FILE]),
    }
    for key, value in expected_digests.items():
        if actual[key] != require_digest(value, key):
            raise ValueError(f"{key}: source_sha256_mismatch")

    validate_markers(
        h_files[HOMOLOGATION_FILE].read_text(encoding="utf-8"),
        p_files[PADRAO_DELIVERY_FILE].read_text(encoding="utf-8"),
        p_files[BACEN_GATE_FILE].read_text(encoding="utf-8"),
    )

    updates = [
        {
            "lane": "homologation",
            "source": str(h_files[HOMOLOGATION_FILE]),
            "target": ALLOWLIST["homologation"][HOMOLOGATION_FILE],
            "sha256": actual["homologation"],
        },
        {
            "lane": "padrao_ouro",
            "source": str(p_files[PADRAO_DELIVERY_FILE]),
            "target": ALLOWLIST["padrao_ouro"][PADRAO_DELIVERY_FILE],
            "sha256": actual["padrao_delivery"],
        },
        {
            "lane": "padrao_ouro",
            "source": str(p_files[BACEN_GATE_FILE]),
            "target": ALLOWLIST["padrao_ouro"][BACEN_GATE_FILE],
            "sha256": actual["bacen_gate"],
        },
    ]
    updates.extend(
        {"lane": "homologation" if "homologation" in item["target"] else "padrao_ouro", **item}
        for item in write_tests(tests_dir)
    )

    return {
        "schema_version": "1.0.0",
        "contract": "governed-workflow-artifact-promotion",
        "decision": "validated",
        "expected_base_sha": base_sha,
        "updates": updates,
        "allowlisted_targets": sorted(item["target"] for item in updates),
        "force_push_allowed": False,
        "direct_main_write_allowed": False,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--homologation-dir", required=True, type=Path)
    parser.add_argument("--padrao-dir", required=True, type=Path)
    parser.add_argument("--homologation-sha256", required=True)
    parser.add_argument("--padrao-delivery-sha256", required=True)
    parser.add_argument("--bacen-gate-sha256", required=True)
    parser.add_argument("--expected-base-sha", required=True)
    parser.add_argument("--tests-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        plan = build_plan(
            args.homologation_dir,
            args.padrao_dir,
            args.expected_base_sha,
            {
                "homologation": args.homologation_sha256,
                "padrao_delivery": args.padrao_delivery_sha256,
                "bacen_gate": args.bacen_gate_sha256,
            },
            args.tests_dir,
        )
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"governed workflow promotion blocked: {exc}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"governed workflow promotion: decision={plan['decision']} updates={len(plan['updates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
