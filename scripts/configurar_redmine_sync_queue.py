#!/usr/bin/env python3
"""Captura e valida ao vivo as informações necessárias para o Redmine Sync
Queue (docs/architecture/redmine-sync-queue.md) — fecha os gaps deixados na
entrega original: nenhuma credencial real configurada, schema de
`cr85a_redminequeue` assumido por convenção (não confirmado no ambiente real),
nada testado contra Dataverse/Redmine de verdade.

Uso:
  python scripts/configurar_redmine_sync_queue.py status
      Mostra o que já está configurado no .env/ambiente (nunca imprime
      segredo em texto puro).

  python scripts/configurar_redmine_sync_queue.py capturar
      Pergunta interativamente cada variável que falta e grava em .env
      (Enter mantém o valor atual). Aceita também flags explícitas, ex.:
      --redmine-base-url https://redmine-c5i6.onrender.com

  python scripts/configurar_redmine_sync_queue.py verificar
      Testa ao vivo: aquisição de token Azure AD/Dataverse, Application User
      do AZURE_CLIENT_ID no ambiente, schema real das tabelas cr85a_* contra
      o que o código assume (incluindo o bloqueador de cr85a_correlationid em
      cr85a_agilesync), e conectividade de leitura com o Redmine.

  python scripts/configurar_redmine_sync_queue.py tudo
      capturar (só o que faltar) + verificar, em sequência.

Nunca imprime AZURE_CLIENT_SECRET/REDMINE_API_KEY em texto puro — apenas
presença/ausência e um preview mascarado.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / 'backend'))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / '.env', override=False)

from app.core.config import Settings  # noqa: E402
from app.services import dataverse_queue_client as dv  # noqa: E402
from app.services.dataverse_queue_client import DataverseError  # noqa: E402
from app.services.redmine_sync_queue import (  # noqa: E402
    TABELA_AGILESYNC,
    TABELA_AUDITLOG,
    TABELA_REDMINE_QUEUE,
)

ENV_FILE = _ROOT / '.env'

# (nome, é_segredo, descrição, ajuda_de_onde_conseguir)
VARIAVEIS: list[tuple[str, bool, str, str]] = [
    ('AZURE_TENANT_ID', False, 'Tenant ID do Azure AD', 'mesmo já usado por Teams Gateway/hub_lowcode — az account show'),
    ('AZURE_CLIENT_ID', False, 'Client ID do App Registration', '"ReqSys Enterprise" ou equivalente no Entra ID'),
    ('AZURE_CLIENT_SECRET', True, 'Client secret do App Registration', 'Entra ID > App Registration > Certificates & secrets'),
    ('REDMINE_BASE_URL', False, 'URL base do Redmine', 'ex.: https://redmine-c5i6.onrender.com'),
    ('REDMINE_API_KEY', True, 'API Key do Redmine', 'scripts/verificar-redmine.ps1 captura automaticamente via login'),
    ('REDMINE_PROJECT_ID', False, 'ID numérico do projeto padrão no Redmine', 'GET /projects.json'),
    (
        'REDMINE_SYNC_DATAVERSE_URL', False,
        'URL do ambiente Dataverse onde vivem as tabelas cr85a_*',
        'ex.: https://orga258f260.crm2.dynamics.com — Maker Portal > ambiente > URL',
    ),
]

# Schema assumido por app/services/redmine_sync_queue.py — confirmado ao vivo
# por este script (comando "verificar") contra o Dataverse real.
COLUNAS_ESPERADAS: dict[str, dict[str, str]] = {
    TABELA_REDMINE_QUEUE: {
        'cr85a_correlationid': 'String',
        'cr85a_plannertaskid': 'String',
        'cr85a_trackercode': 'String',
        'cr85a_trackerid': 'Integer',
        'cr85a_subject': 'String',
        'cr85a_status': 'String',
        'cr85a_reservedat': 'DateTime',
        'cr85a_retrycount': 'Integer',
        'cr85a_errordetail': 'Memo',
    },
    TABELA_AGILESYNC: {
        'cr85a_correlationid': 'String',
        'cr85a_plannertaskid': 'String',
        'cr85a_trackercode': 'String',
        'cr85a_trackerid': 'Integer',
        'cr85a_plannertitle': 'String',
        'cr85a_plannerstatus': 'String',
    },
    TABELA_AUDITLOG: {
        'cr85a_correlationid': 'String',
        'cr85a_evento': 'String',
        'cr85a_origem': 'String',
        'cr85a_dataevento': 'DateTime',
        'cr85a_sucesso': 'Boolean',
    },
}
COLUNAS_OPCIONAIS: dict[str, set[str]] = {TABELA_REDMINE_QUEUE: {'cr85a_redmineissueid'}}


def _linha(texto: str = '') -> None:
    print(texto)


def _titulo(texto: str) -> None:
    _linha()
    _linha('=' * 78)
    _linha(f' {texto}')
    _linha('=' * 78)


def _flag_dest(nome: str) -> str:
    return nome.lower()


def cmd_status(_args: argparse.Namespace) -> int:
    _titulo('Status das variáveis necessárias — Redmine Sync Queue')
    faltando = []
    for nome, _segredo, descricao, _ajuda in VARIAVEIS:
        valor = os.environ.get(nome, '')
        if valor:
            # Não propague valores vindos do ambiente para stdout. Além de
            # segredos explícitos, IDs/URLs podem ser classificados como
            # sensíveis pelo scanner e não são necessários para o diagnóstico.
            _linha(f'  [OK]     {nome:<28} configurado')
        else:
            _linha(f'  [FALTA]  {nome:<28} {descricao}')
            faltando.append(nome)
    _linha()
    if faltando:
        _linha(f'  {len(faltando)} variável(is) faltando. Rode: python {Path(__file__).name} capturar')
        return 1
    _linha('  Todas as variáveis necessárias estão presentes. Rode "verificar" para testar ao vivo.')
    return 0


def _atualizar_env_file(pares: dict[str, str]) -> None:
    conteudo = ENV_FILE.read_text(encoding='utf-8') if ENV_FILE.exists() else ''
    for chave, valor in pares.items():
        padrao = re.compile(rf'^{re.escape(chave)}=.*$', re.MULTILINE)
        linha_nova = f'{chave}={valor}'
        if padrao.search(conteudo):
            conteudo = padrao.sub(linha_nova, conteudo)
        else:
            conteudo = conteudo.rstrip('\n') + ('\n' if conteudo else '') + f'{linha_nova}\n'
    ENV_FILE.write_text(conteudo, encoding='utf-8')


def cmd_capturar(args: argparse.Namespace) -> int:
    _titulo('Captura de credenciais — Redmine Sync Queue')
    valores: dict[str, str] = {}
    for nome, segredo, descricao, ajuda in VARIAVEIS:
        atual = os.environ.get(nome, '')
        valor_cli = getattr(args, _flag_dest(nome), None)
        if valor_cli:
            valores[nome] = valor_cli
            continue
        if atual and not args.forcar:
            continue

        _linha(f'\n{nome} — {descricao}')
        _linha(f'  (onde conseguir: {ajuda})')
        if segredo:
            novo = getpass.getpass('  Valor (entrada oculta, Enter para manter atual): ')
        else:
            novo = input(f'  Valor [{atual or "vazio"}]: ').strip()
        if novo:
            valores[nome] = novo

    if not valores:
        _linha('\nNenhum valor novo informado — nada gravado.')
        return 0

    _atualizar_env_file(valores)
    for chave, valor in valores.items():
        os.environ[chave] = valor
    _linha(f'\n[OK] {len(valores)} variável(is) gravada(s) em {ENV_FILE}')
    return 0


def _get_redmine_json(base_url: str, path: str, api_key: str) -> Any:
    request = urllib.request.Request(
        f'{base_url.rstrip("/")}{path}',
        headers={'X-Redmine-API-Key': api_key, 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=15) as resp:  # nosec B310 - URL do operador via .env
        return json.loads(resp.read().decode('utf-8'))


async def _verificar_dataverse(cfg: Settings, erros: list[str]) -> None:
    _titulo('1) Azure AD -> token Dataverse')
    if not (cfg.azure_tenant_id and cfg.azure_client_id and cfg.azure_client_secret):
        _linha('  [FALTA] AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET incompleto(s).')
        erros.append('azure_ad_incompleto')
        return
    if not cfg.redmine_sync_dataverse_url:
        _linha('  [FALTA] REDMINE_SYNC_DATAVERSE_URL não configurado.')
        erros.append('dataverse_url_ausente')
        return

    try:
        token = await dv.testar_autenticacao(cfg.redmine_sync_dataverse_url)
        _linha(f'  [OK] Token adquirido ({len(token)} caracteres).')
    except Exception as exc:
        _linha(f'  [FALHA] {exc}')
        erros.append('token_dataverse')
        return

    _titulo('2) Application User no Dataverse (AZURE_CLIENT_ID)')
    try:
        info = await dv.verificar_application_user(cfg.redmine_sync_dataverse_url, cfg.azure_client_id)
        if info['existe']:
            _linha(f'  [OK] Application User existe (systemuserid={info["systemuserid"]}).')
        else:
            _linha('  [FALTA] Nenhum Application User para este AZURE_CLIENT_ID neste ambiente.')
            _linha('          Rode (um humano com Power Platform Admin):')
            _linha(f'          pac admin application register --application-id {cfg.azure_client_id}')
            _linha(
                f'          pac admin assign-user --environment {cfg.redmine_sync_dataverse_url} '
                f'--user {cfg.azure_client_id} --role "System Customizer" --application-user'
            )
            erros.append('application_user_ausente')
    except DataverseError as exc:
        _linha(f'  [FALHA] {exc}')
        erros.append('application_user_check')

    _titulo('3) Schema real das tabelas cr85a_* vs. assumido no código')
    for tabela, esperadas in COLUNAS_ESPERADAS.items():
        try:
            reais = await dv.listar_colunas(cfg.redmine_sync_dataverse_url, tabela)
        except DataverseError as exc:
            _linha(f'\n  Tabela: {tabela}\n    [FALHA] {exc}')
            erros.append(f'schema_{tabela}')
            continue

        reais_por_nome = {c['LogicalName']: c.get('AttributeType') for c in reais}
        opcionais = COLUNAS_OPCIONAIS.get(tabela, set())
        _linha(f'\n  Tabela: {tabela}')
        for coluna, tipo_esperado in esperadas.items():
            if coluna not in reais_por_nome:
                if coluna in opcionais:
                    _linha(f'    [OPCIONAL-FALTA] {coluna} (esperado {tipo_esperado})')
                else:
                    _linha(f'    [FALTA]          {coluna} (esperado {tipo_esperado})')
                    erros.append(f'coluna_ausente_{tabela}_{coluna}')
            elif reais_por_nome[coluna] != tipo_esperado:
                _linha(f'    [DIVERGENTE]     {coluna}: real={reais_por_nome[coluna]} esperado={tipo_esperado}')
                erros.append(f'coluna_divergente_{tabela}_{coluna}')
            else:
                _linha(f'    [OK]             {coluna}')

        if tabela == TABELA_AGILESYNC and 'cr85a_correlationid' in reais_por_nome:
            diag = await dv.metadados_coluna(cfg.redmine_sync_dataverse_url, tabela, 'cr85a_correlationid')
            max_length = diag.get('max_length')
            if max_length is not None and max_length < 36:
                _linha(f'    [BLOQUEADOR]     cr85a_correlationid MaxLength={max_length} (precisa de >= 36 para um guid())')
                erros.append('correlationid_truncando')
            elif max_length is not None:
                _linha(f'    [OK]             cr85a_correlationid MaxLength={max_length} (>= 36)')


def _verificar_redmine(cfg: Settings, erros: list[str], criar_issue_teste: bool) -> None:
    _titulo('4) Redmine (REDMINE_BASE_URL / REDMINE_API_KEY / REDMINE_PROJECT_ID)')
    base_url = os.environ.get('REDMINE_BASE_URL', '').strip()
    api_key = os.environ.get('REDMINE_API_KEY', '').strip()
    project_id = os.environ.get('REDMINE_PROJECT_ID', '').strip()

    if not (base_url and api_key and project_id):
        _linha('  [FALTA] REDMINE_BASE_URL/REDMINE_API_KEY/REDMINE_PROJECT_ID incompleto(s).')
        erros.append('redmine_incompleto')
        return

    try:
        quem = _get_redmine_json(base_url, '/users/current.json', api_key)
        _linha(f'  [OK] API Key válida — logado como {quem.get("user", {}).get("login", "?")}.')
    except urllib.error.HTTPError as exc:
        _linha(f'  [FALHA] REDMINE_API_KEY inválida: HTTP {exc.code}')
        erros.append('redmine_api_key_invalida')
        return
    except urllib.error.URLError as exc:
        _linha(f'  [FALHA] Não foi possível conectar em {base_url}: {exc.reason}')
        erros.append('redmine_offline')
        return

    try:
        projeto = _get_redmine_json(base_url, f'/projects/{project_id}.json', api_key)
        _linha(f'  [OK] Projeto {project_id} existe: {projeto.get("project", {}).get("name", "?")}')
    except urllib.error.HTTPError as exc:
        _linha(f'  [FALHA] REDMINE_PROJECT_ID={project_id} inválido: HTTP {exc.code}')
        erros.append('redmine_project_id_invalido')
        return

    if criar_issue_teste:
        from app.services.github_redmine import IntegracaoError, criar_issue_generica

        try:
            resultado = criar_issue_generica(
                subject='[ReqSys] teste de conectividade redmine_sync_queue',
                description=(
                    'Issue criada automaticamente por scripts/configurar_redmine_sync_queue.py '
                    'verificar --criar-issue-teste — pode ser fechada/excluída.'
                ),
            )
            _linha(f'  [OK] Issue de teste REAL criada: {resultado["redmine_url"]} (remova manualmente se desejar).')
        except IntegracaoError as exc:
            _linha(f'  [FALHA] Criação de issue real falhou: {exc}')
            erros.append('redmine_criar_issue')
    else:
        _linha('  [PULADO] Criação de issue real não testada (use --criar-issue-teste para validar de ponta a ponta).')


def cmd_verificar(args: argparse.Namespace) -> int:
    cfg = Settings()  # instância fresca: reflete o .env mais recente, não o singleton importado no processo
    erros: list[str] = []

    asyncio.run(_verificar_dataverse(cfg, erros))
    _verificar_redmine(cfg, erros, criar_issue_teste=args.criar_issue_teste)

    _titulo('Resumo')
    if erros:
        _linha(f'  {len(erros)} problema(s) encontrado(s):')
        for item in erros:
            _linha(f'    - {item}')
        _linha('\n  Corrija os itens acima e rode "verificar" novamente.')
        return 1
    _linha('  Tudo verificado com sucesso — pronto para usar /v1/redmine-sync.')
    return 0


def cmd_tudo(args: argparse.Namespace) -> int:
    codigo = cmd_capturar(args)
    if codigo != 0:
        return codigo
    # processo novo garante Settings()/dotenv carregando o .env recém-gravado,
    # em vez de depender de invalidar singletons já importados neste processo.
    resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), 'verificar'] + (
        ['--criar-issue-teste'] if args.criar_issue_teste else []
    ))
    return resultado.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='comando', required=True)

    p_status = sub.add_parser('status', help='Mostra o que já está configurado (sem imprimir segredo).')
    p_status.set_defaults(func=cmd_status)

    p_capturar = sub.add_parser('capturar', help='Pergunta o que falta e grava em .env.')
    p_capturar.add_argument('--forcar', action='store_true', help='Pergunta mesmo para variáveis já configuradas.')
    for nome, _segredo, descricao, _ajuda in VARIAVEIS:
        p_capturar.add_argument(f'--{nome.lower().replace("_", "-")}', dest=_flag_dest(nome), default=None, help=descricao)
    p_capturar.set_defaults(func=cmd_capturar)

    p_verificar = sub.add_parser('verificar', help='Testa tudo ao vivo: Azure AD, Dataverse, schema, Redmine.')
    p_verificar.add_argument(
        '--criar-issue-teste', action='store_true',
        help='Também cria uma issue REAL de teste no Redmine (efeito colateral real — off por padrão).',
    )
    p_verificar.set_defaults(func=cmd_verificar)

    p_tudo = sub.add_parser('tudo', help='capturar + verificar em sequência.')
    p_tudo.add_argument('--forcar', action='store_true')
    p_tudo.add_argument('--criar-issue-teste', action='store_true')
    for nome, _segredo, descricao, _ajuda in VARIAVEIS:
        p_tudo.add_argument(f'--{nome.lower().replace("_", "-")}', dest=_flag_dest(nome), default=None, help=descricao)
    p_tudo.set_defaults(func=cmd_tudo)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
