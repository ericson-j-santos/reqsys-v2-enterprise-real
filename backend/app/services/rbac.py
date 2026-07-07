from enum import Enum

PERMISSOES_POR_PAPEL = {
    'admin': [
        'dashboard:read',
        'requisitos:write',
        'rastreabilidade:read',
        'auditoria:read',
        'relatorios:read',
        'demanda:iniciar',
        'demanda:cancelar',
        'demanda:aprovar',
        'demanda:arquivar',
        'servico:executar',
        'servico:cancelar',
        'servico:aprovar',
        'dossie:criar',
        'dossie:iniciar',
        'dossie:aprovar',
        'dossie:arquivar',
    ],
    'analista': [
        'dashboard:read',
        'requisitos:write',
        'rastreabilidade:read',
        'relatorios:read',
        'demanda:iniciar',
        'servico:executar',
        'dossie:criar',
        'dossie:iniciar',
    ],
    'auditor': [
        'dashboard:read',
        'rastreabilidade:read',
        'auditoria:read',
        'relatorios:read',
        'dossie:aprovar',
    ],
    'gestor': [
        'dashboard:read',
        'requisitos:write',
        'rastreabilidade:read',
        'relatorios:read',
        'demanda:iniciar',
        'demanda:aprovar',
        'servico:executar',
        'servico:aprovar',
        'dossie:criar',
        'dossie:iniciar',
        'dossie:aprovar',
    ],
}


class PapelPadrao(str, Enum):
    """Taxonomia de papeis padrao (ADR-004): VIEWER, ANALYST, ADMIN, SECURITY,
    RUNTIME_OPERATOR, AI_GOVERNOR.

    Os papeis legados abaixo (`admin`, `analista`, `auditor`, `gestor`) continuam
    sendo os valores emitidos em JWTs e usados pelo frontend hoje — nao sao
    renomeados aqui para nao invalidar sessoes/tokens ja emitidos. Esta taxonomia
    e uma camada de compatibilidade: `papel_canonico()` traduz um papel legado para
    o nome padrao, e `permissoes()`/`tem_permissao()` aceitam tanto o nome legado
    quanto o canonico como entrada.
    """

    VIEWER = 'VIEWER'
    ANALYST = 'ANALYST'
    ADMIN = 'ADMIN'
    SECURITY = 'SECURITY'
    RUNTIME_OPERATOR = 'RUNTIME_OPERATOR'
    AI_GOVERNOR = 'AI_GOVERNOR'


# Mapeamento do papel legado (valor real hoje em JWT/frontend) para o papel
# padrao ADR-004 correspondente.
PAPEL_LEGADO_PARA_PADRAO: dict[str, PapelPadrao] = {
    'admin': PapelPadrao.ADMIN,
    'analista': PapelPadrao.ANALYST,
    'auditor': PapelPadrao.SECURITY,
    'gestor': PapelPadrao.RUNTIME_OPERATOR,
}

# Papeis da taxonomia ADR-004 sem equivalente legado direto: precisam de um
# conjunto de permissoes proprio (nao herdado de PERMISSOES_POR_PAPEL).
PERMISSOES_EXTRA_PADRAO: dict[PapelPadrao, list[str]] = {
    PapelPadrao.VIEWER: [
        'dashboard:read',
        'rastreabilidade:read',
        'relatorios:read',
    ],
    PapelPadrao.AI_GOVERNOR: [
        'dashboard:read',
        'rastreabilidade:read',
        'auditoria:read',
        'ia:governanca:read',
        'ia:governanca:aprovar',
    ],
}


def _chave_legado(papel: str) -> str | None:
    """Resolve `papel` (legado ou canonico ADR-004) para a chave legado em PERMISSOES_POR_PAPEL."""
    if papel in PERMISSOES_POR_PAPEL:
        return papel
    papel_upper = (papel or '').upper()
    for legado, padrao in PAPEL_LEGADO_PARA_PADRAO.items():
        if padrao.value == papel_upper:
            return legado
    return None


def papel_canonico(papel: str) -> str:
    """Traduz um papel (legado ou ja canonico) para a taxonomia padrao ADR-004."""
    if papel in PAPEL_LEGADO_PARA_PADRAO:
        return PAPEL_LEGADO_PARA_PADRAO[papel].value
    papel_upper = (papel or '').upper()
    if papel_upper in PapelPadrao.__members__:
        return papel_upper
    return papel


def permissoes(papel: str) -> list[str]:
    chave_legado = _chave_legado(papel)
    if chave_legado is not None:
        return PERMISSOES_POR_PAPEL[chave_legado]

    papel_upper = (papel or '').upper()
    for padrao, escopos in PERMISSOES_EXTRA_PADRAO.items():
        if padrao.value == papel_upper:
            return escopos
    return []


def tem_permissao(papel: str, escopo: str) -> bool:
    return escopo in permissoes(papel)
