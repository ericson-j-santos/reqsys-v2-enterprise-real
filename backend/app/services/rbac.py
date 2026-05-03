PERMISSOES_POR_PAPEL = {
    'admin': ['dashboard:read','requisitos:write','rastreabilidade:read','auditoria:read','relatorios:read'],
    'analista': ['dashboard:read','requisitos:write','rastreabilidade:read','relatorios:read'],
    'auditor': ['dashboard:read','rastreabilidade:read','auditoria:read','relatorios:read'],
}

def permissoes(papel: str):
    return PERMISSOES_POR_PAPEL.get(papel, [])
