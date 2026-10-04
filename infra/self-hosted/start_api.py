"""Load mounted secrets without logging values or placing them in arguments."""
import os
import re
from pathlib import Path
from urllib.parse import quote


def read_secret(root: Path, name: str) -> str:
    value = (root / name).read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("database_secret_invalid")
    return value


def read_literal_secret(root: Path, name: str, required: bool = True) -> str:
    raw = (root / name).read_bytes()
    if len(raw) > 65536:
        raise ValueError("runtime_secret_size_invalid")
    value = raw.decode("utf-8")
    if "\x00" in value or (required and not value):
        raise ValueError("runtime_secret_invalid")
    return value


def configure(root: Path) -> None:
    password = read_secret(root, "db_app_password")
    mode = os.environ.get("REQSYS_REQUIRE_RUNTIME_KEY_HANDOFF", "")
    if mode not in ("", "0", "1"):
        raise ValueError("runtime_key_handoff_mode_invalid")
    migrated = mode == "1"
    # The migration uses exact effective source strings. Fresh portable stacks
    # retain the original three-secret contract and its hex64 JWT validation.
    token = (read_literal_secret(root, "jwt_secret") if migrated
             else read_secret(root, "jwt_secret"))
    pass_path = root / "cofre_keyring_passphrase"
    ai_path = root / "ai_conversation_content_encryption_key_b64"
    passphrase = (read_literal_secret(root, "cofre_keyring_passphrase", required=migrated)
                  if migrated or pass_path.exists() else None)
    ai_key = (read_literal_secret(root, "ai_conversation_content_encryption_key_b64", required=False)
              if migrated or ai_path.exists() else None)
    os.environ["DATABASE_URL"] = (
        f"postgresql+psycopg2://reqsys_app:{quote(password, safe='')}@db:5432/reqsys"
    )
    os.environ["JWT_SECRET"] = token
    if passphrase is not None:
        os.environ["COFRE_KEYRING_PASSPHRASE"] = passphrase
    if ai_key is not None:
        if ai_key:
            os.environ["AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64"] = ai_key
        else:
            os.environ.pop("AI_CONVERSATION_CONTENT_ENCRYPTION_KEY_B64", None)


if __name__ == "__main__":
    configure(Path("/run/secrets"))
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
