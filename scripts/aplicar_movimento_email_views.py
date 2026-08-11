#!/usr/bin/env python3
"""Aplica (ou reverte) as views de origem versionadas do e-mail Prospecção
Movimento — Portabilidade Consignado (#2861) no SQL Server corporativo.

Artefato autocontido: só usa stdlib + `pyodbc` (já é dependência do
projeto) — sem Flyway/Liquibase/nenhuma ferramenta externa. Os arquivos
`.sql` e o `MANIFEST.json` vivem em
`backend/app/services/movimento_email/sql/views/` (ver README.md lá para a
convenção de versionamento e o motivo de V1 ser um stub — GAP #2861-1,
schema real ainda não confirmado com a equipe de dados).

  python scripts/aplicar_movimento_email_views.py status
      Recalcula o SHA-256 de cada arquivo .sql e compara com MANIFEST.json —
      não conecta em nada. Detecta se alguém editou uma versão já "fechada"
      sem seguir a convenção (nova versão = novo arquivo V<N+1>__...).

  python scripts/aplicar_movimento_email_views.py aplicar [--dry-run]
      Aplica, em ordem, todos os arquivos V<N>__vw_*.sql via
      `CREATE OR ALTER VIEW` (idempotente) dentro de uma única transação.
      --dry-run só valida checksums e mostra o plano, sem conectar no banco.

  python scripts/aplicar_movimento_email_views.py rollback --confirmar [--dry-run]
      Executa V<N>__rollback.sql (DROP VIEW IF EXISTS — idempotente) da
      versão mais recente. Destrutivo; exige --confirmar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS_DIR = _ROOT / 'backend' / 'app' / 'services' / 'movimento_email' / 'sql' / 'views'
_MANIFEST_PATH = _VIEWS_DIR / 'MANIFEST.json'

sys.path.insert(0, str(_ROOT / 'backend'))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / '.env', override=False)

from app.core.config import Settings  # noqa: E402


def _linha(texto: str = '') -> None:
    print(texto)


def _titulo(texto: str) -> None:
    _linha()
    _linha('=' * 78)
    _linha(f' {texto}')
    _linha('=' * 78)


def _carregar_manifest() -> dict:
    if not _MANIFEST_PATH.is_file():
        raise SystemExit(f'MANIFEST.json não encontrado em {_MANIFEST_PATH}')
    return json.loads(_MANIFEST_PATH.read_text(encoding='utf-8'))


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _validar_checksums(manifest: dict) -> list[str]:
    """Recalcula o hash de cada arquivo listado no manifesto e compara.
    Retorna a lista de problemas encontrados (vazia = tudo OK)."""
    problemas: list[str] = []
    for versao in manifest['versoes']:
        arquivos = list(versao['arquivos']) + [versao['rollback']]
        for entrada in arquivos:
            caminho = _VIEWS_DIR / entrada['arquivo']
            if not caminho.is_file():
                problemas.append(f'{entrada["arquivo"]}: arquivo ausente (esperado pelo manifesto, versão {versao["versao"]})')
                continue
            hash_real = _sha256(caminho)
            if hash_real != entrada['sha256']:
                problemas.append(
                    f'{entrada["arquivo"]}: checksum divergente do manifesto (versão {versao["versao"]} deveria ser imutável — '
                    f'se a mudança é intencional, crie uma nova versão em vez de editar esta)'
                )
    return problemas


def cmd_status(_args: argparse.Namespace) -> int:
    _titulo('Status — views de origem Movimento Email (#2861)')
    manifest = _carregar_manifest()
    problemas = _validar_checksums(manifest)
    for versao in manifest['versoes']:
        _linha(f'  Versão {versao["versao"]}: {versao["descricao"]}')
        for entrada in versao['arquivos']:
            marcador = '[OK]' if not any(entrada['arquivo'] in p for p in problemas) else '[DIVERGE]'
            _linha(f'    {marcador:<10} {entrada["arquivo"]}')
    _linha()
    if problemas:
        _linha(f'  {len(problemas)} problema(s):')
        for p in problemas:
            _linha(f'    - {p}')
        return 1
    _linha('  Checksums batem com MANIFEST.json. Rode "aplicar" para publicar no SQL Server.')
    return 0


def _plano_aplicacao(manifest: dict) -> list[Path]:
    arquivos: list[Path] = []
    for versao in manifest['versoes']:
        for entrada in versao['arquivos']:
            arquivos.append(_VIEWS_DIR / entrada['arquivo'])
    return arquivos


def cmd_aplicar(args: argparse.Namespace) -> int:
    _titulo('Aplicar views de origem — Movimento Email (#2861)')
    manifest = _carregar_manifest()
    problemas = _validar_checksums(manifest)
    if problemas:
        _linha('  Checksum inválido — abortando antes de tocar no banco:')
        for p in problemas:
            _linha(f'    - {p}')
        return 1

    plano = _plano_aplicacao(manifest)
    _linha('  Plano (nesta ordem, cada arquivo é um único CREATE OR ALTER VIEW):')
    for caminho in plano:
        _linha(f'    - {caminho.name}')

    if args.dry_run:
        _linha('\n  --dry-run: nada foi conectado nem executado.')
        return 0

    cfg = Settings()
    if not cfg.movimento_email_source_dsn:
        _linha('\n  [ERRO] MOVIMENTO_EMAIL_SOURCE_DSN não configurado — rode com --dry-run para só validar, '
               'ou configure o DSN (ver scripts/verificar_movimento_email_fontes.py status).')
        return 1

    try:
        import pyodbc
    except ImportError:
        _linha('\n  [ERRO] Pacote "pyodbc" não instalado. Rode: pip install -r backend/requirements.txt')
        return 1

    _linha('\n  Conectando e aplicando dentro de uma única transação...')
    try:
        conexao = pyodbc.connect(cfg.movimento_email_source_dsn, timeout=cfg.movimento_email_query_timeout_seconds, autocommit=False)
    except pyodbc.Error as exc:
        _linha(f'  [ERRO] Falha ao conectar: {exc}')
        return 1

    try:
        cursor = conexao.cursor()
        for caminho in plano:
            cursor.execute(caminho.read_text(encoding='utf-8'))
            _linha(f'    [OK] {caminho.name}')
        conexao.commit()
    except pyodbc.Error as exc:
        conexao.rollback()
        _linha(f'  [ERRO] Falha ao aplicar — transação revertida integralmente: {exc}')
        return 1
    finally:
        conexao.close()

    _titulo('Resumo')
    _linha(f'  {len(plano)} view(s) aplicada(s) com sucesso (idempotente — pode rodar de novo a qualquer momento).')
    _linha('  Rode scripts/verificar_movimento_email_fontes.py verificar para confirmar ao vivo.')
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    _titulo('Rollback — views de origem Movimento Email (#2861)')
    if not args.confirmar:
        _linha('  Operação destrutiva (DROP VIEW). Rode de novo com --confirmar para prosseguir.')
        return 1

    manifest = _carregar_manifest()
    ultima_versao = manifest['versoes'][-1]
    caminho_rollback = _VIEWS_DIR / ultima_versao['rollback']['arquivo']

    if _sha256(caminho_rollback) != ultima_versao['rollback']['sha256']:
        _linha(f'  [ERRO] Checksum de {caminho_rollback.name} diverge do manifesto — abortando.')
        return 1

    _linha(f'  Vai executar: {caminho_rollback.name}')
    if args.dry_run:
        _linha('  --dry-run: nada foi conectado nem executado.')
        return 0

    cfg = Settings()
    if not cfg.movimento_email_source_dsn:
        _linha('  [ERRO] MOVIMENTO_EMAIL_SOURCE_DSN não configurado.')
        return 1

    import pyodbc

    try:
        conexao = pyodbc.connect(cfg.movimento_email_source_dsn, timeout=cfg.movimento_email_query_timeout_seconds, autocommit=False)
    except pyodbc.Error as exc:
        _linha(f'  [ERRO] Falha ao conectar: {exc}')
        return 1

    try:
        cursor = conexao.cursor()
        cursor.execute(caminho_rollback.read_text(encoding='utf-8'))
        conexao.commit()
    except pyodbc.Error as exc:
        conexao.rollback()
        _linha(f'  [ERRO] Falha no rollback — transação revertida: {exc}')
        return 1
    finally:
        conexao.close()

    _linha('  Rollback aplicado com sucesso.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='comando', required=True)

    p_status = sub.add_parser('status', help='Valida checksums locais contra MANIFEST.json (não conecta em nada).')
    p_status.set_defaults(func=cmd_status)

    p_aplicar = sub.add_parser('aplicar', help='Aplica as views no SQL Server (idempotente).')
    p_aplicar.add_argument('--dry-run', action='store_true', help='Só valida e mostra o plano, sem conectar.')
    p_aplicar.set_defaults(func=cmd_aplicar)

    p_rollback = sub.add_parser('rollback', help='Remove as views (DROP VIEW IF EXISTS) — destrutivo.')
    p_rollback.add_argument('--confirmar', action='store_true', help='Necessário para prosseguir com a remoção.')
    p_rollback.add_argument('--dry-run', action='store_true', help='Só mostra o plano, sem conectar.')
    p_rollback.set_defaults(func=cmd_rollback)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
