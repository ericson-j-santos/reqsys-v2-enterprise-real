"""Inicializa segredos em diretorio privado, sem sobrescrever valores existentes."""
import argparse
import os
import secrets
from pathlib import Path

def initialize(root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix" and root.stat().st_mode & 0o077:
        raise ValueError("Diretorio de segredos exige modo 0700")
    count = 0
    for name in ("db_owner_password", "db_app_password", "jwt_secret"):
        try:
            fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w") as out:
            out.write(secrets.token_hex(32) + "\n")
        count += 1
    return count

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    print(f"Arquivos criados: {initialize(args.directory)}; valores nao exibidos")
