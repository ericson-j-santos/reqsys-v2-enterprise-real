from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_ocr_local_fallback_parity.py"
SPEC = importlib.util.spec_from_file_location("ocr_local_fallback_parity", MODULE_PATH)
assert SPEC and SPEC.loader
parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parity)

LOCAL = ROOT / "backend" / "ocr_evidencia"
WORKFLOW = ROOT / ".github" / "workflows" / "ocr-benchmark.yml"


def test_local_fallback_has_only_expected_python_surface() -> None:
    files = set(parity._python_files(LOCAL))
    assert files == {
        "__init__.py",
        "adaptadores/__init__.py",
        "adaptadores/ocr_tesseract.py",
        "dominio/__init__.py",
        "dominio/nome.py",
    }


def test_local_root_init_is_declarative_and_versioned() -> None:
    contract = parity.validate_root_init(LOCAL / "__init__.py")
    assert contract == {"version": "1.2.0", "all": ["__version__"]}


def test_byte_drift_is_detected(tmp_path: Path) -> None:
    local = tmp_path / "local"
    engine = tmp_path / "engine"
    shutil.copytree(LOCAL, local)
    shutil.copytree(LOCAL, engine)
    target = local / "dominio" / "nome.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# drift-control\n", encoding="utf-8")

    with pytest.raises(parity.ParityError, match="python_drift:dominio/nome.py"):
        parity.compare_python_tree(local, engine)


def test_root_init_docstring_difference_is_allowed(tmp_path: Path) -> None:
    local = tmp_path / "local"
    engine = tmp_path / "engine"
    shutil.copytree(LOCAL, local)
    shutil.copytree(LOCAL, engine)
    init = engine / "__init__.py"
    init.write_text(
        '"""Docstring diferente no fornecedor."""\n'
        '__version__ = "1.2.0"\n'
        '__all__ = ["__version__"]\n',
        encoding="utf-8",
    )

    report = parity.compare_python_tree(local, engine)
    assert report["root_init_semantic_parity"] is True
    assert "__init__.py" not in report["byte_identical_files"]


def test_root_init_extra_executable_statement_is_rejected(tmp_path: Path) -> None:
    init = tmp_path / "__init__.py"
    init.write_text(
        '"""snapshot"""\n'
        'import os\n'
        '__version__ = "1.2.0"\n'
        '__all__ = ["__version__"]\n',
        encoding="utf-8",
    )

    with pytest.raises(parity.ParityError, match="root_init_executable_statement"):
        parity.validate_root_init(init)


def test_benchmark_workflow_runs_parity_before_external_install() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    names = [
        "Isolar a cópia local e provar ausência do pacote",
        "Preparar pacote OCR canônico e reproduzível",
        "Validar paridade do fallback local com engine pinado",
        "Controle negativo de drift do fallback local",
        "Instalar somente o wheel canônico verificado",
    ]
    positions = [text.index(name) for name in names]
    assert positions == sorted(positions)
    assert "validate_ocr_local_fallback_parity.py" in text
    assert "OCR_LOCAL_FALLBACK_DRIFT_NEGATIVE_CONTROL_OK" in text
