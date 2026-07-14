#!/usr/bin/env python3
"""Verifica o comprimento de secrets sensiveis no Fly.io sem nunca ler ou imprimir o valor real.

flyctl secrets list nao expoe valores (por design da Fly), entao a unica forma
de confirmar que um secret atende a um requisito minimo (ex.: JWT_SECRET com
>=32 caracteres) e executar `flyctl ssh console` na propria maquina e medir o
comprimento da variavel de ambiente la dentro - sem nunca fazer echo do valor.

Uso:
    python scripts/check_fly_secret_strength.py --app reqsys-api \
        --key JWT_SECRET --min-length 32 \
        --key JWT_ISSUER --min-length 1 \
        --key JWT_AUDIENCE --min-length 1
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretCheck:
    key: str
    min_length: int


def _build_remote_command(checks: list[SecretCheck]) -> str:
    parts = []
    for check in checks:
        parts.append(f'printf "%s " "{check.key}"; eval "printf %s \\"\\${check.key}\\"" | wc -c')
    return " ; ".join(parts)


def executar(app: str, checks: list[SecretCheck], *, fly_bin: str = "flyctl") -> dict[str, int]:
    remote_cmd = _build_remote_command(checks)
    completed = subprocess.run(
        [fly_bin, "ssh", "console", "--app", app, "-C", f"sh -c '{remote_cmd}'"],
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"flyctl ssh console falhou (codigo {completed.returncode}): {completed.stderr.strip()}"
        )
    lengths: dict[str, int] = {}
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line or " " not in line:
            continue
        key, _, raw_len = line.rpartition(" ")
        key = key.strip()
        try:
            # printf "%s" nao emite newline, entao wc -c conta exatamente o
            # comprimento do valor da variavel, sem ajuste.
            lengths[key] = int(raw_len.strip())
        except ValueError:
            continue
    return lengths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, help="Nome do app Fly.io (ex.: reqsys-api)")
    parser.add_argument(
        "--key",
        action="append",
        dest="keys",
        default=[],
        help="Nome da env var a verificar (repita a flag para varias)",
    )
    parser.add_argument(
        "--min-length",
        action="append",
        dest="min_lengths",
        type=int,
        default=[],
        help="Comprimento minimo esperado, na mesma ordem/quantidade de --key",
    )
    parser.add_argument("--fly-bin", default="flyctl")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.keys:
        print("Informe ao menos um --key", file=sys.stderr)
        return 2
    if len(args.keys) != len(args.min_lengths):
        print("--key e --min-length devem ter a mesma quantidade", file=sys.stderr)
        return 2

    checks = [SecretCheck(key, min_len) for key, min_len in zip(args.keys, args.min_lengths)]
    try:
        lengths = executar(args.app, checks, fly_bin=args.fly_bin)
    except RuntimeError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    ok = True
    for check in checks:
        length = lengths.get(check.key)
        if length is None:
            print(f"{check.key}: nao encontrado/vazio no ambiente remoto -> FALHA")
            ok = False
            continue
        status = "ok" if length >= check.min_length else "FALHA"
        if status == "FALHA":
            ok = False
        print(f"{check.key}: comprimento={length} (minimo={check.min_length}) -> {status}")

    print(f"resultado_geral={'ok' if ok else 'action_required'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
