"""Carrega segredos montados sem grava-los em logs ou argumentos."""
import os
import re
from pathlib import Path
from urllib.parse import quote

def read_secret(root: Path, name: str) -> str:
    value = (root / name).read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"Segredo invalido: {name}; exige 32 bytes hex aleatorios")
    return value

def configure(root: Path) -> None:
    password = read_secret(root, "db_app_password")
    token = read_secret(root, "jwt_secret")
    os.environ["DATABASE_URL"] = (
        f"postgresql+psycopg2://reqsys_app:{quote(password, safe='')}@db:5432/reqsys"
    )
    os.environ["JWT_SECRET"] = token

if __name__ == "__main__":
    configure(Path("/run/secrets"))
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
