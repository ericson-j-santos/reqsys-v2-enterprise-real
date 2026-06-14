#!/usr/bin/env python3
"""
Inicializa o cofre e grava segredos interativamente ou a partir do .env.

Uso:
  python scripts/vault_setup.py init              # cria master key
  python scripts/vault_setup.py init --force      # recria (invalida segredos existentes)
  python scripts/vault_setup.py set KEY VALUE     # grava um segredo
  python scripts/vault_setup.py get KEY           # lê e imprime um segredo (stdout limpo)
  python scripts/vault_setup.py delete KEY        # remove um segredo
  python scripts/vault_setup.py status            # exibe estado do vault
  python scripts/vault_setup.py import-env        # importa segredos do .env para o vault
  python scripts/vault_setup.py gen-token         # gera um VAULT_API_TOKEN aleatório

Exemplo de uso em shell scripts:
  DB_PASS=$(python scripts/vault_setup.py get DATABASE_PASSWORD)
  export GITHUB_TOKEN=$(python scripts/vault_setup.py get GITHUB_TOKEN)
"""

import sys
import os
from pathlib import Path

# Adiciona o backend ao path para importar app.core.secrets diretamente
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

# Carrega .env antes de importar o módulo de segredos
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)

from app.core.secrets import (
    init_vault,
    vault_initialized,
    write_secret_to_vault,
    delete_secret_from_vault,
    read_secret_from_vault,
    _vault_service_name,
)


def cmd_init(force: bool = False):
    service = _vault_service_name()
    if vault_initialized() and not force:
        print(f'[OK] Vault "{service}" já está inicializado.')
        print('     Use --force para recriar a master key (invalida todos os segredos existentes).')
        return
    ok = init_vault(overwrite=force)
    if ok:
        print(f'[OK] Vault "{service}" inicializado com nova master key.')
    else:
        print('[ERRO] Não foi possível inicializar o vault (keyring ou cryptography indisponíveis).')
        sys.exit(1)


def cmd_set(key: str, value: str):
    try:
        write_secret_to_vault(key, value)
        print(f'[OK] Segredo "{key}" gravado no vault.')
    except RuntimeError as exc:
        print(f'[ERRO] {exc}')
        sys.exit(1)


def cmd_get(key: str):
    """Imprime o valor do segredo para stdout (limpo, capturável por scripts)."""
    value = read_secret_from_vault(key)
    if value is None:
        print(f'[ERRO] Segredo "{key}" não encontrado no vault ou vault não inicializado.', file=sys.stderr)
        sys.exit(1)
    print(value)


def cmd_delete(key: str):
    removed = delete_secret_from_vault(key)
    if removed:
        print(f'[OK] Segredo "{key}" removido do vault.')
    else:
        print(f'[AVISO] Segredo "{key}" não encontrado no vault.')


def cmd_status():
    service = _vault_service_name()
    init = vault_initialized()
    print(f'Service : {service}')
    print(f'Estado  : {"INICIALIZADO" if init else "NÃO INICIALIZADO"}')


def cmd_import_env():
    env_path = Path(__file__).resolve().parents[1] / '.env'
    if not env_path.exists():
        print(f'[ERRO] {env_path} não encontrado.')
        sys.exit(1)

    skip = {'REQSYS_VAULT_SERVICE_NAME', 'VAULT_API_TOKEN', 'VITE_API_URL',
            'BACKEND_PORT', 'FRONTEND_PORT', 'GATEWAY_PORT', 'SDD_SPECS_PATH', 'KB_DB_PATH'}
    imported = 0
    with open(env_path, encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip()
            if key in skip or not val:
                continue
            try:
                write_secret_to_vault(key, val)
                print(f'  [OK] {key}')
                imported += 1
            except RuntimeError as exc:
                print(f'  [ERRO] {key}: {exc}')
    print(f'\n{imported} segredo(s) importado(s) para o vault.')


def cmd_gen_token():
    import secrets
    token = secrets.token_urlsafe(32)
    print(f'VAULT_API_TOKEN={token}')
    print('\nAdicione esta linha ao seu .env')


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == 'init':
        cmd_init(force='--force' in args)
    elif cmd == 'set':
        if len(args) < 3:
            print('Uso: vault_setup.py set KEY VALUE')
            sys.exit(1)
        cmd_set(args[1], args[2])
    elif cmd == 'get':
        if len(args) < 2:
            print('Uso: vault_setup.py get KEY')
            sys.exit(1)
        cmd_get(args[1])
    elif cmd == 'delete':
        if len(args) < 2:
            print('Uso: vault_setup.py delete KEY')
            sys.exit(1)
        cmd_delete(args[1])
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'import-env':
        cmd_import_env()
    elif cmd == 'gen-token':
        cmd_gen_token()
    else:
        print(f'Comando desconhecido: {cmd}')
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
