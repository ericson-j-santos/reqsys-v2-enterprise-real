#!/usr/bin/env python3
"""CI check: detect mojibake patterns in Python source files.

Usage:
    python scripts/check_encoding.py
    python scripts/check_encoding.py backend/app/api backend/app/services

Exit codes:
    0 — no mojibake found
    1 — mojibake found (prints file:line for each hit)
"""
import sys
from pathlib import Path

MOJIBAKE_PATTERNS = ["Ã§", "Ã£", "Ã©", "Ã¡", "Ãº", "Ã³", "Ã\xad", "Ã\xa3"]

DEFAULT_TARGETS = [
    Path("backend/app/api"),
    Path("backend/app/services"),
]


def scan(targets: list[Path]) -> list[str]:
    hits: list[str] = []
    for target in targets:
        for py_file in sorted(target.rglob("*.py")):
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"AVISO: não foi possível ler {py_file}: {exc}", file=sys.stderr)
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern in MOJIBAKE_PATTERNS:
                    if pattern in line:
                        hits.append(f"{py_file}:{lineno}: mojibake detectado: {pattern!r}")
                        break
    return hits


def main() -> None:
    raw_targets = sys.argv[1:] or None
    targets = [Path(t) for t in raw_targets] if raw_targets else DEFAULT_TARGETS

    missing = [t for t in targets if not t.exists()]
    if missing:
        for m in missing:
            print(f"ERRO: diretório não encontrado: {m}", file=sys.stderr)
        sys.exit(2)

    hits = scan(targets)

    if hits:
        print("ERRO: Strings com mojibake encontradas — corrija o encoding antes do commit:\n")
        for hit in hits:
            print(f"  {hit}")
        sys.exit(1)

    total = sum(len(list(t.rglob("*.py"))) for t in targets)
    print(f"OK — {total} arquivo(s) verificado(s), nenhum mojibake encontrado.")


if __name__ == "__main__":
    main()
