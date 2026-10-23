import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mutmut_configuration_keeps_the_golden_test_focused() -> None:
    config = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))

    mutmut = config["tool"]["mutmut"]
    assert mutmut["source_paths"] == ["app"]
    assert mutmut["only_mutate"] == ["app/core/*"]
    assert mutmut["pytest_add_cli_args_test_selection"] == ["tests"]


def test_golden_test_uses_the_pinned_mutmut_3_cli() -> None:
    workflow = (ROOT / ".github" / "workflows" / "golden-test-advanced.yml").read_text(
        encoding="utf-8"
    )

    assert "'mutmut==3.8.0'" in workflow
    assert "mutmut run\n" in workflow
    assert "--paths-to-mutate" not in workflow
    assert "--tests-dir" not in workflow
    assert "--runner" not in workflow
