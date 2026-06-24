# Runbook — Operational Health Dashboard

## Quando usar

Use este runbook quando houver:

- muitos PRs abertos;
- PRs draft antigos;
- conflitos recorrentes;
- falhas visuais antigas no GitHub Actions;
- necessidade de decidir se um PR deve ser mergeado, fechado ou recriado.

## Fluxo recomendado

```text
Listar PRs abertos
→ classificar por estado operacional
→ calcular merge readiness score
→ fechar superseded/duplicados
→ recriar branches antigas quando necessário
→ priorizar production-ready
→ validar CI
→ merge controlado
```

## Decisão por classe

| Classe | Ação padrão |
|---|---|
| production-ready | Validar CI e mergear |
| governance-only | Validar escopo e mergear se não houver risco |
| experimental | Manter draft ou fechar se antigo |
| blocked | Corrigir ou recriar branch limpa |
| superseded | Fechar com justificativa |

## Checklist antes do merge

- PR fora de draft.
- CI principal verde.
- PR Conflict Guard verde.
- PR CI Watch verde.
- Governance Quality Gates verde.
- Branch Protection Audit verde.
- Sem alteração produtiva não autorizada.
- Merge readiness score estimado maior ou igual a 85.

## Checklist para fechar PR obsoleto

- Confirmar se o escopo já está na main.
- Confirmar se há PR posterior equivalente.
- Atualizar corpo do PR com motivo.
- Fechar sem merge.
- Recriar branch limpa apenas se necessário.

## Links operacionais

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
- Pull Requests: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pulls
