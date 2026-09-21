from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "fabric-identity-readonly-probe.yml"
)


def test_fabric_identity_probe_is_read_only_and_sanitized() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "environment: reqsys-power-platform-dev" in text
    assert "permissions:\n  contents: read" in text
    assert "pull_request_target" not in text
    assert "secret_value_exposed=false" in text
    assert "client_secret" in text
    assert "print(secret)" not in text
    assert "print(client_secret)" not in text
    assert "print(pat)" not in text
    assert "Authorization: f\"Bearer {pat}\"" not in text


def test_fabric_identity_probe_has_bounded_execution_and_sanitized_artifact() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "timeout-minutes: 10" in text
    assert "if: always()" in text
    assert "artifacts/fabric-identity-probe.json" in text
    assert "retention-days: 7" in text
    assert '"secret_value_exposed": False' in text
