#!/usr/bin/env python3
"""Stub fail-closed do antigo verificador remoto de secrets do Fly.io.

O comando anterior abria um shell remoto e interpolava nomes fornecidos pelo
operador. Apos a aposentadoria do provedor, nenhuma sessao SSH e permitida.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

FLYIO_RETIREMENT_GUARD = (
    "Fly.io foi retirado definitivamente em 2026-10-02; "
    "inspecao de secrets por shell remoto esta bloqueada."
)


@dataclass(frozen=True)
class SecretCheck:
    key: str
    min_length: int


def executar(
    app: str, checks: list[SecretCheck], *, fly_bin: str = "flyctl"
) -> dict[str, int]:
    raise RuntimeError(FLYIO_RETIREMENT_GUARD)


def main() -> int:
    print(FLYIO_RETIREMENT_GUARD, file=sys.stderr)
    return 78


if __name__ == "__main__":
    raise SystemExit(main())
