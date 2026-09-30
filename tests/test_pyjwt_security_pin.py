from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "backend" / "requirements-audit.txt",
    ROOT / "backend" / "requirements.txt",
    ROOT / "backend" / "token_broker" / "requirements.txt",
)


def test_pyjwt_security_pin_is_consistent_and_patched() -> None:
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        assert "PyJWT==2.15.0" in text, path
        assert "PyJWT==2.14.0" not in text, path
        assert "PyJWT==2.13.0" not in text, path
