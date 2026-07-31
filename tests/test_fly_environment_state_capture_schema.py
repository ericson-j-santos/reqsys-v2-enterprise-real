import json
from pathlib import Path


def test_capture_schema_forbids_secret_values() -> None:
    schema = json.loads(
        Path("docs/contracts/fly-environment-state-capture.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["secret_values_persisted"]["const"] is False
    assert schema["properties"]["environment"]["enum"] == ["dev", "hml", "prod"]
