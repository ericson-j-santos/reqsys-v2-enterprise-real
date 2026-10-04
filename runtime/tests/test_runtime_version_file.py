from pathlib import Path


def test_runtime_version_file_matches_increment() -> None:
    version_file = Path(__file__).resolve().parents[1] / "VERSION"

    assert version_file.read_text(encoding="utf-8").strip() == "0.7.1"
