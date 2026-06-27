from __future__ import annotations

from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agile_runtime import AgileWorkItem
from app.models.requisito import Requisito
from app.services.agile_ai_router import recomendar_roteamento_multi_ia
from app.services.git_parser import inferir_ambiente_branch

_AMBIENTE_ALIASES: dict[str, str] = {
    'dev': 'dev',
    'desenvolvimento': 'dev',
    'development': 'dev',
    'local': 'dev',
    'test': 'test',
    'testes': 'test',
    'testing': 'test',
    'teste': 'test',
    'homolog': 'homolog',
    'hml': 'homolog',
    'staging': 'homolog',
    'stg': 'homolog',
    'homologacao': 'homolog',
    'prod': 'prod',
    'producao': 'prod',
    'production': 'prod',
}

_BRANCH_BASE: dict[str, str] = {
    'dev': 'dev',
    'test': 'dev',
    'homolog': 'hml',
    'prod': 'main',
}

_CONFIG_AMBIENTE_KEY: dict[str, str] = {
    'dev': 'desenvolvimento',
    'test': 'testes',
    'homolog': 'homologacao',
    'prod': 'producao',
}


def normalizar_ambiente_launchpad(ambiente: str) -> str:
    chave = (ambiente or 'dev').strip().lower().replace('-', '_')
    resultado = _AMBIENTE_ALIASES.get(chave)
    if not resultado:
        raise ValueError(f'Ambiente invalido: {ambiente}')
    return resultado


def branch_base_por_ambiente(ambiente: str) -> str:
    return _BRANCH_BASE[normalizar_ambiente_launchpad(ambiente)]


def _resolver_repositorio(item: AgileWorkItem) -> str:
    return (item.repositorio or settings.github_alm_repo or '').strip()


def _resolver_branch_trabalho(item: AgileWorkItem, ambiente: str) -> str:
    amb = normalizar_ambiente_launchpad(ambiente)
    if amb == 'prod':
        return branch_base_por_ambiente(amb)
    if amb == 'homolog':
        if item.ambiente_deploy == 'homolog' and item.branch:
            return item.branch
        return branch_base_por_ambiente(amb)
    if item.branch:
        return item.branch
    return recomendar_roteamento_multi_ia(item).branch_sugerida


def _acoes_disponiveis(ambiente: str) -> list[str]:
    amb = normalizar_ambiente_launchpad(ambiente)
    if amb in {'dev', 'test'}:
        return ['abrir_branch', 'criar_branch_github', 'abrir_pr', 'ver_actions', 'abrir_app']
    if amb == 'homolog':
        return ['abrir_branch', 'abrir_pr', 'ver_actions', 'abrir_app']
    return ['abrir_branch', 'abrir_app']


def _github_url_repo(repo: str) -> str:
    return f'https://github.com/{repo}'


def _github_url_tree(repo: str, branch: str) -> str:
    return f'{_github_url_repo(repo)}/tree/{quote(branch, safe="/")}'


def _github_url_compare(
    repo: str,
    base: str,
    head: str,
    *,
    expand: bool = False,
    quick_pull: bool = False,
) -> str:
    url = f'{_github_url_repo(repo)}/compare/{quote(base, safe="/")}...{quote(head, safe="/")}'
    params: list[str] = []
    if expand:
        params.append('expand=1')
    if quick_pull:
        params.append('quick_pull=1')
    if params:
        url += '?' + '&'.join(params)
    return url


def _github_url_actions(repo: str, branch: str) -> str:
    encoded = quote(f'branch:{branch}', safe='')
    return f'{_github_url_repo(repo)}/actions?query={encoded}'


def _url_app_ambiente(ambiente: str) -> str | None:
    amb = normalizar_ambiente_launchpad(ambiente)
    config_key = _CONFIG_AMBIENTE_KEY[amb]
    info = settings.ambientes_urls.get(config_key)
    if not info:
        return None
    return info.get('frontend')


def _buscar_requisito_codigo(db: Session | None, requisito_id: int | None) -> str | None:
    if not db or not requisito_id:
        return None
    requisito = db.get(Requisito, requisito_id)
    return requisito.codigo if requisito else None


def montar_github_launchpad(
    item: AgileWorkItem,
    ambiente: str,
    db: Session | None = None,
) -> dict:
    amb = normalizar_ambiente_launchpad(ambiente)
    repo = _resolver_repositorio(item)
    if not repo:
        raise ValueError('Repositorio GitHub nao configurado para o work item')

    branch_base = branch_base_por_ambiente(amb)
    branch_trabalho = _resolver_branch_trabalho(item, amb)
    requisito_codigo = _buscar_requisito_codigo(db, item.requisito_id)

    links: dict[str, str | None] = {
        'branch': _github_url_tree(repo, branch_trabalho),
        'criar_branch': _github_url_compare(repo, branch_base, branch_trabalho, expand=True),
        'novo_pr': _github_url_compare(repo, branch_base, branch_trabalho, quick_pull=True),
        'actions': _github_url_actions(repo, branch_trabalho),
        'app_ambiente': _url_app_ambiente(amb),
        'repositorio': _github_url_repo(repo),
    }
    if item.change_url:
        links['change_request'] = item.change_url
    if item.ci_url:
        links['ci'] = item.ci_url
    if item.deploy_url:
        links['deploy'] = item.deploy_url

    mensagem_commit = f'feat({item.codigo}): {item.titulo}'
    if requisito_codigo:
        mensagem_commit += f' [{requisito_codigo}]'

    return {
        'work_item_id': item.id,
        'work_item_codigo': item.codigo,
        'requisito_codigo': requisito_codigo,
        'ambiente': amb,
        'ambiente_branch_inferido': inferir_ambiente_branch(branch_trabalho),
        'repositorio': repo,
        'branch_trabalho': branch_trabalho,
        'branch_base': branch_base,
        'branch_existe': None,
        'links': links,
        'acoes_disponiveis': _acoes_disponiveis(amb),
        'somente_leitura': amb == 'prod',
        'mensagem_commit_sugerida': mensagem_commit,
        'notas': [
            'P0: links read-only; criacao de branch via API GitHub fica para fase posterior.',
            'Validar increment gate antes de criar branch ou PR em ambiente compartilhado.',
        ],
    }
