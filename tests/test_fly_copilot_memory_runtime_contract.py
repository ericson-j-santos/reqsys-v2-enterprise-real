from pathlib import Path


def test_copilot_memory_runtime_sources_exist() -> None:
    assert Path("backend/copilot_memory_core/__init__.py").is_file()
    assert Path("backend/copilot_memory_powerautomate_complete.py").is_file()
    assert Path("backend/copilot_memory_simple_package.py").is_file()
