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


def permissoes(papel: str) -> list[str]:
    return PERMISSOES_POR_PAPEL.get(papel, [])


def tem_permissao(papel: str, escopo: str) -> bool:
    return escopo in permissoes(papel)
