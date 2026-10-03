import zipfile
from pathlib import Path

import pytest

from scripts.homologate_copilot_hitl_dev_components import REQUIRED_TOKENS, homologate


def _write_package(path: Path, *, omit: str | None = None) -> None:
    tokens = [token for group in REQUIRED_TOKENS.values() for token in group if token != omit]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("customizations.xml", "<root>" + "\n".join(tokens) + "</root>")


def test_homologates_complete_dev_export(tmp_path: Path) -> None:
    solutions = tmp_path / "solutions.txt"
    solutions.write_text("ReqSysCopilotHITL 1.0.0.0", encoding="utf-8")
    package = tmp_path / "solution.zip"
    _write_package(package)

    evidence = homologate(solutions, package)

    assert evidence["status"] == "HOMOLOGATED"
    assert evidence["missing_components"] == []
    assert evidence["stg_prod_promotion_allowed"] is False


def test_blocks_solution_absent_from_dev(tmp_path: Path) -> None:
    solutions = tmp_path / "solutions.txt"
    solutions.write_text("OtherSolution", encoding="utf-8")
    package = tmp_path / "solution.zip"
    _write_package(package)

    with pytest.raises(ValueError, match="não localizada"):
        homologate(solutions, package)


def test_blocks_missing_component(tmp_path: Path) -> None:
    solutions = tmp_path / "solutions.txt"
    solutions.write_text("ReqSysCopilotHITL", encoding="utf-8")
    package = tmp_path / "solution.zip"
    _write_package(package, omit="ReqSys Supervisor")

    with pytest.raises(ValueError, match="agents:ReqSys Supervisor"):
        homologate(solutions, package)


def test_blocks_invalid_zip(tmp_path: Path) -> None:
    solutions = tmp_path / "solutions.txt"
    solutions.write_text("ReqSysCopilotHITL", encoding="utf-8")
    package = tmp_path / "solution.zip"
    package.write_text("invalid", encoding="utf-8")

    with pytest.raises(ValueError, match="ZIP válido"):
        homologate(solutions, package)
