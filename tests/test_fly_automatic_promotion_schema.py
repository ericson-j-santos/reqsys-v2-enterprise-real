import json
from pathlib import Path


def test_report_schema_blocks_stale_sha_and_production_bypass() -> None:
    schema = json.loads(
        Path("docs/contracts/fly-automatic-environment-promotion.schema.json").read_text(
            encoding="utf-8"
        )
    )
    properties = schema["properties"]
    assert properties["stale_sha_promotion_allowed"]["const"] is False
    assert properties["production_gate_bypass_allowed"]["const"] is False
    assert properties["automatic_order"]["const"] == ["dev", "hml", "prod"]
