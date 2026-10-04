from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "security-specialized-scanners.yml"
)


def test_sbom_syft_download_is_pinned_retried_and_verified() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'SYFT_VERSION: "1.51.0"' in text
    assert 'SYFT_ARCHIVE_SHA256: "2a2e837a2c8d59ec9af5472ee22d3b04ee463c4e44476ecf993fd1e5ab6ebc7f"' in text
    assert "--retry 5 --retry-delay 2 --retry-all-errors" in text
    assert "sha256sum --check -" in text
    assert "anchore/sbom-action@v0" not in text


def test_sbom_generation_remains_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'SYFT_CHECK_FOR_APP_UPDATE: "false"' in text
    assert "syft . -o cyclonedx-json=artifacts/security-scanners/sbom/reqsys-sbom.cyclonedx.json" in text
    assert "test -s artifacts/security-scanners/sbom/reqsys-sbom.cyclonedx.json" in text
    assert "if-no-files-found: error" in text
