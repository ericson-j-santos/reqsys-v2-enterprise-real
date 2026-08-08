#!/usr/bin/env python3
"""Valida termos de domínio em arquivos alterados, sem dependências externas."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXTENSOES_ANALISADAS = {
    ".cs", ".html", ".java", ".js", ".jsx", ".md", ".py", ".sql",
    ".ts", ".tsx", ".vue", ".yaml", ".yml",
}
DIRETORIOS_IGNORADOS = {".git", "dist", "node_modules", "vendor"}
ARQUIVOS_DE_GOVERNANCA = {
    "docs/governanca/GLOSSARIO-CANONICO.md",
    "docs/governanca/POLITICA-IDIOMA.md",
    "governance/idioma/termos.json",
}


def carregar_contrato(caminho: Path) -> dict[str, object]:
    try:
        contrato = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ValueError(f"Não foi possível carregar {caminho}: {erro}") from erro

    if contrato.get("idioma_principal") != "pt-BR":
        raise ValueError("O contrato deve declarar idioma_principal como pt-BR.")
    if not isinstance(contrato.get("termos_de_dominio"), dict):
        raise ValueError("O contrato deve conter termos_de_dominio.")
    return contrato


def deve_analisar(caminho: Path) -> bool:
    return (
        caminho.suffix.lower() in EXTENSOES_ANALISADAS
        and not any(parte in DIRETORIOS_IGNORADOS for parte in caminho.parts)
        and caminho.as_posix() not in ARQUIVOS_DE_GOVERNANCA
    )


def localizar_termos(caminho: Path, termos: dict[str, str]) -> list[tuple[int, str, str]]:
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    ocorrencias: list[tuple[int, str, str]] = []
    for numero, linha in enumerate(linhas, start=1):
        for termo_externo, termo_canonico in termos.items():
            padrao = rf"(?<![A-Za-z]){re.escape(termo_externo)}(?![A-Za-z])"
            if re.search(padrao, linha, flags=re.IGNORECASE):
                ocorrencias.append((numero, termo_externo, termo_canonico))
    return ocorrencias


def executar(arquivos: list[str], contrato_path: Path, bloquear: bool) -> int:
    try:
        contrato = carregar_contrato(contrato_path)
    except ValueError as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 2

    termos = contrato["termos_de_dominio"]
    total = 0
    for nome in sorted(set(arquivos)):
        caminho = Path(nome)
        if not caminho.is_file() or not deve_analisar(caminho):
            continue
        for linha, externo, canonico in localizar_termos(caminho, termos):
            total += 1
            print(
                f"AVISO: {caminho}:{linha}: termo '{externo}' encontrado; "
                f"considere '{canonico}'."
            )

    print(f"Validação de idioma concluída: {total} aviso(s); modo={'bloqueante' if bloquear else 'consultivo'}.")
    return 1 if bloquear and total else 0


def principal() -> int:
    parser = argparse.ArgumentParser(description="Valida a política de português primeiro.")
    parser.add_argument("arquivos", nargs="*", help="Arquivos a analisar.")
    parser.add_argument(
        "--contrato",
        type=Path,
        default=Path("governance/idioma/termos.json"),
        help="Caminho do contrato de termos.",
    )
    parser.add_argument(
        "--bloquear",
        action="store_true",
        help="Retorna falha quando houver termos não canônicos.",
    )
    argumentos = parser.parse_args()
    return executar(argumentos.arquivos, argumentos.contrato, argumentos.bloquear)


if __name__ == "__main__":
    raise SystemExit(principal())
