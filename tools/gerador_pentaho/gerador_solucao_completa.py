#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Empacotador da aplicacao de treinamento Pentaho (fluxo de criacao de dossie).

Versao do gerador: 2.0.0
Aplicacao empacotada: pacote/ (fluxo sintetico de dossie, compativel com
Pentaho Data Integration 7.1+ via Kitchen/Spoon)

Ate a versao 1.1.0 (`gerador_solucao_completa_v2.1.0.py`, fora deste
repositorio) este script embarcava a aplicacao inteira como um blob base64
dentro do proprio arquivo .py, validado contra um SHA-256 fixo. A partir
desta versao a fonte de verdade passa a ser o diretorio versionado
`pacote/`, ao lado deste script: revisavel arquivo a arquivo, diffavel em
PR e testavel sem decodificar nada. Este script apenas materializa esse
diretorio para um destino (copia real, para rodar localmente ou com o
Pentaho Data Integration) e, opcionalmente, empacota um ZIP portatil para
distribuicao fora do controle de versao (ex.: anexar a um chamado, enviar
a quem so tem acesso ao Pentaho).

Dados exclusivamente sinteticos (ADR-002 / LGPD): nenhum endpoint, segredo,
identificador pessoal ou nome de sistema interno real e usado em `pacote/`.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ_GERADOR = Path(__file__).resolve().parent
PACOTE_DIR = RAIZ_GERADOR / "pacote"
NOME_APLICACAO = "pacote-treino-fluxo-dossie-pentaho"


class ErroGeracao(RuntimeError):
    """Erro esperado de uso (destino invalido, dependencia ausente etc.)."""


def _arquivos_do_pacote() -> list[Path]:
    if not PACOTE_DIR.is_dir():
        raise ErroGeracao(f"PACOTE_NAO_ENCONTRADO:{PACOTE_DIR}")
    return sorted(caminho for caminho in PACOTE_DIR.rglob("*") if caminho.is_file())


def listar() -> int:
    for caminho in _arquivos_do_pacote():
        print(caminho.relative_to(PACOTE_DIR).as_posix())
    return 0


def calcular_sha256(caminho: Path) -> str:
    hasher = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            hasher.update(bloco)
    return hasher.hexdigest()


def gerar_diretorio(destino: Path, forcar: bool) -> Path:
    _arquivos_do_pacote()
    destino = destino.resolve()
    if destino.exists():
        if not forcar:
            raise ErroGeracao(f"DESTINO_JA_EXISTE:{destino}")
        shutil.rmtree(destino)
    shutil.copytree(PACOTE_DIR, destino)
    print(f"APLICACAO_GERADA={destino}")
    return destino


def gerar_zip(destino: Path, forcar: bool) -> Path:
    arquivos = _arquivos_do_pacote()
    destino = destino.resolve()
    if destino.exists() and not forcar:
        raise ErroGeracao(f"ZIP_JA_EXISTE:{destino}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        for caminho in arquivos:
            arcname = Path(NOME_APLICACAO) / caminho.relative_to(PACOTE_DIR)
            arquivo_zip.write(caminho, arcname=arcname.as_posix())
    print(f"ZIP_GERADO={destino}")
    print(f"SHA256_GERADO={calcular_sha256(destino)}")
    return destino


def executar_testes(raiz: Path) -> int:
    arquivo_teste = raiz / "testes" / "fluxo.test.js"
    if not arquivo_teste.is_file():
        raise ErroGeracao(f"TESTE_NAO_ENCONTRADO:{arquivo_teste}")
    try:
        concluido = subprocess.run(
            ["node", "--test", str(arquivo_teste)],
            cwd=raiz,
            check=False,
        )
    except FileNotFoundError as erro:
        raise ErroGeracao("NODE_NAO_ENCONTRADO: instale Node.js 18+") from erro
    return concluido.returncode


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Empacota a aplicacao de treinamento Pentaho (fluxo de criacao "
            "de dossie) versionada em tools/gerador_pentaho/pacote/."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista os arquivos do pacote sem gerar nada.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / NOME_APLICACAO,
        help="Diretorio de saida da aplicacao gerada.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve o destino (--output ou --zip) se ja existir.",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        help="Tambem grava um ZIP portatil no caminho informado.",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Executa os testes Node.js da aplicacao gerada (requer Node.js 18+).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = criar_parser().parse_args(argv)
    if argumentos.dry_run:
        return listar()

    raiz = gerar_diretorio(argumentos.output, argumentos.force)
    if argumentos.zip:
        gerar_zip(argumentos.zip, argumentos.force)
    if argumentos.run_tests:
        return executar_testes(raiz)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ErroGeracao as erro:
        print(f"ERRO={erro}", file=sys.stderr)
        raise SystemExit(2)
