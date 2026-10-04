from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def test_current_dependency_security_floors_are_patched() -> None:
    backend = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    audit = (ROOT / "backend" / "requirements-audit.txt").read_text(encoding="utf-8")
    broker = (ROOT / "backend" / "token_broker" / "requirements.txt").read_text(encoding="utf-8")
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert "PyJWT==2.15.0" in backend
    assert "PyJWT==2.15.0" in audit
    assert "PyJWT==2.15.0" in broker
    assert "urllib3==2.8.0" in backend
    assert "urllib3==2.8.0" in audit
    assert package["dependencies"]["axios"] == "^1.20.0"
    assert package["dependencies"]["dompurify"] == "^3.4.16"


def test_vulnerable_dependency_floors_do_not_return() -> None:
    paths = (
        ROOT / "backend" / "requirements.txt",
        ROOT / "backend" / "requirements-audit.txt",
        ROOT / "backend" / "token_broker" / "requirements.txt",
        ROOT / "frontend" / "package.json",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for vulnerable in (
        "PyJWT==2.14.0",
        "urllib3==2.7.0",
        '"axios": "^1.19.0"',
        '"dompurify": "^3.4.13"',
    ):
        assert vulnerable not in combined
