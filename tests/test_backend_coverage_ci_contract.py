from pathlib import Path


WORKFLOW = Path(".github/workflows/ci.yml")


def test_backend_coverage_uses_explicit_config_for_subprocesses() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    backend_test = workflow[workflow.index("\n  backend-test:\n"):]
    command = backend_test[backend_test.index("python -m pytest tests/"):]
    command = command[:command.index("2>&1 | tee")]

    assert "--cov=app" in command
    assert "--cov-config=pyproject.toml" in command
    assert command.index("--cov-config=pyproject.toml") < command.index("--cov-report=")
