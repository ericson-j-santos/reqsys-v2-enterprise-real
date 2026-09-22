import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sdd_gate", ROOT / "scripts" / "sdd_gate.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_spec(root: Path, *, tests=True, acceptance=True):
    specs = root / ".sdd" / "specs"
    specs.mkdir(parents=True)
    (specs / "feature.spec.json").write_text(
        '{"feature_name":"feature","approvals":{"requirements":true},"sdd_gate":{"tests":['
        + ('"tests/test_feature.py"' if tests else '') + ']}}', encoding="utf-8")
    text = "# Requisitos\n## Critérios de aceite\n1. deve funcionar" if acceptance else "# Requisitos"
    (specs / "feature.requirements.md").write_text(text, encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_feature.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

def test_blocks_functional_change_without_spec(tmp_path):
    ok, detail = MODULE.validate(tmp_path, ["backend/app/api/x.py"], "abc")
    assert ok is False
    assert "SDD_SPEC_REQUIRED" in detail


def test_accepts_complete_contract(tmp_path):
    write_spec(tmp_path)
    files = ["backend/app/api/x.py", ".sdd/specs/feature.spec.json"]
    assert MODULE.validate(tmp_path, files, "abc") == MODULE.validate(tmp_path, files, "abc")
    ok, detail = MODULE.validate(tmp_path, files, "abc")
    assert ok is True
    assert "SDD_OK head=abc" in detail


def test_blocks_missing_acceptance_criteria(tmp_path):
    write_spec(tmp_path, acceptance=False)
    ok, detail = MODULE.validate(tmp_path, ["scripts/x.py", ".sdd/specs/feature.spec.json"], "abc")
    assert ok is False
    assert "critérios de aceite ausentes" in detail


def test_docs_only_does_not_require_spec(tmp_path):
    assert MODULE.validate(tmp_path, ["docs/readme.md"], "abc")[0] is True


def test_deleted_spec_does_not_count_as_current_contract(tmp_path):
    ok, detail = MODULE.validate(
        tmp_path,
        ["scripts/x.py", ".sdd/specs/removed.spec.json"],
        "abc",
    )
    assert ok is False
    assert "SDD_SPEC_REQUIRED" in detail


def test_deleted_old_spec_is_ignored_when_new_spec_exists(tmp_path):
    write_spec(tmp_path)
    files = [
        "scripts/x.py",
        ".sdd/specs/removed.spec.json",
        ".sdd/specs/feature.spec.json",
    ]
    ok, detail = MODULE.validate(tmp_path, files, "abc")
    assert ok is True
    assert "SDD_OK head=abc specs=1" in detail
