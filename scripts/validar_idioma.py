#!/usr/bin/env python3
"""Valida termos de domínio e gera evidência estruturada, sem dependências externas."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def carregar_contrato(caminho: Path) -> dict[str, Any]:
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


def localizar_termos(caminho: Path, termos: dict[str, str]) -> list[dict[str, Any]]:
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    ocorrencias: list[dict[str, Any]] = []
    for numero, linha in enumerate(linhas, start=1):
        for termo_externo, termo_canonico in termos.items():
            padrao = rf"(?<![A-Za-z]){re.escape(termo_externo)}(?![A-Za-z])"
            if re.search(padrao, linha, flags=re.IGNORECASE):
                ocorrencias.append(
                    {
                        "arquivo": caminho.as_posix(),
                        "linha": numero,
                        "termo_encontrado": termo_externo,
                        "termo_canonico": termo_canonico,
                    }
                )
    return ocorrencias


def construir_relatorio(
    arquivos: list[str], contrato: dict[str, Any], bloquear: bool
) -> dict[str, Any]:
    termos: dict[str, str] = contrato["termos_de_dominio"]
    analisados: list[str] = []
    ocorrencias: list[dict[str, Any]] = []

    for nome in sorted(set(arquivos)):
        caminho = Path(nome)
        if not caminho.is_file() or not deve_analisar(caminho):
            continue
        analisados.append(caminho.as_posix())
        ocorrencias.extend(localizar_termos(caminho, termos))

    arquivos_com_aviso = sorted({item["arquivo"] for item in ocorrencias})
    total_analisados = len(analisados)
    conformes = total_analisados - len(arquivos_com_aviso)
    taxa = round((conformes / total_analisados) * 100, 2) if total_analisados else 100.0

    return {
        "versao_relatorio": "1.0.0",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "idioma_principal": contrato["idioma_principal"],
        "modo": "bloqueante" if bloquear else "consultivo",
        "metricas": {
            "arquivos_analisados": total_analisados,
            "arquivos_conformes": conformes,
            "arquivos_com_aviso": len(arquivos_com_aviso),
            "ocorrencias": len(ocorrencias),
            "taxa_conformidade_percentual": taxa,
        },
        "arquivos_analisados": analisados,
        "ocorrencias": ocorrencias,
    }


def gravar_relatorio(caminho: Path, relatorio: dict[str, Any]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def executar(
    arquivos: list[str], contrato_path: Path, bloquear: bool, saida_json: Path | None
) -> int:
    try:
        contrato = carregar_contrato(contrato_path)
    except ValueError as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 2

    relatorio = construir_relatorio(arquivos, contrato, bloquear)
    for item in relatorio["ocorrencias"]:
        print(
            f"AVISO: {item['arquivo']}:{item['linha']}: termo "
            f"'{item['termo_encontrado']}' encontrado; considere "
            f"'{item['termo_canonico']}'."
        )

    if saida_json:
        try:
            gravar_relatorio(saida_json, relatorio)
        except OSError as erro:
            print(f"ERRO: não foi possível gravar {saida_json}: {erro}", file=sys.stderr)
            return 2

    metricas = relatorio["metricas"]
    print(
        "Validação de idioma concluída: "
        f"{metricas['ocorrencias']} aviso(s), "
        f"{metricas['taxa_conformidade_percentual']}% de conformidade; "
        f"modo={relatorio['modo']}."
    )
    return 1 if bloquear and metricas["ocorrencias"] else 0


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
        "--saida-json",
        type=Path,
        help="Grava métricas e ocorrências em JSON.",
    )
    parser.add_argument(
        "--bloquear",
        action="store_true",
        help="Retorna falha quando houver termos não canônicos.",
    )
    argumentos = parser.parse_args()
    return executar(
        argumentos.arquivos,
        argumentos.contrato,
        argumentos.bloquear,
        argumentos.saida_json,
    )


if __name__ == "__main__":
    raise SystemExit(principal())
