from __future__ import annotations

import json
from pathlib import Path

from tools.product_intelligence.generate_runtime_ops_governance_p1 import (
    build_environment_matrix,
    build_payload,
)


def test_environment_matrix_is_provider_neutral() -> None:
    matrix = build_environment_matrix()

    assert [item["environment"] for item in matrix] == ["dev", "hml", "prod"]
    assert all(
        "FLY_API_TOKEN" not in item["secret_fingerprints_required"]
        for item in matrix
    )


def test_generated_payload_and_documentation_have_no_active_fly_references() -> None:
    payload = json.dumps(build_payload(), ensure_ascii=False).lower()
    source = Path(
        "tools/product_intelligence/generate_runtime_ops_governance_p1.py"
    ).read_text(encoding="utf-8").lower()

    assert "fly.io" not in payload
    assert "flyio" not in payload
    assert "fly_api_token" not in source
    assert "fly.io" not in source
