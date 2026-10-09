#!/usr/bin/env python3
"""Mudança funcional descartável usada pelo controle negativo de SDD da issue 1759."""


def marker() -> str:
    return "sdd-negative-control"


if __name__ == "__main__":
    print(marker())
