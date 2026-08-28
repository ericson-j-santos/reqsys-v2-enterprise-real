from pathlib import Path


DOCKERFILE = Path("backend/Dockerfile.fly")


def text() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def test_fly_image_contains_copilot_memory_runtime_dependencies() -> None:
    dockerfile = text()

    assert "COPY copilot_memory_core /app/copilot_memory_core" in dockerfile
    assert (
        "COPY copilot_memory_powerautomate_complete.py "
        "/app/copilot_memory_powerautomate_complete.py"
    ) in dockerfile
    assert (
        "COPY copilot_memory_simple_package.py "
        "/app/copilot_memory_simple_package.py"
    ) in dockerfile


def test_copilot_memory_runtime_sources_exist() -> None:
    assert Path("backend/copilot_memory_core/__init__.py").is_file()
    assert Path("backend/copilot_memory_powerautomate_complete.py").is_file()
    assert Path("backend/copilot_memory_simple_package.py").is_file()
