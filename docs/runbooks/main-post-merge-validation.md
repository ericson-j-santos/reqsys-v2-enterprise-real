# Main Post-Merge Validation — Runbook

## Objetivo

Automatizar a validação obrigatória pós-merge da branch `main`, garantindo que o commit resultante tenha evidência objetiva antes de ser considerado estabilizado.

## Validações obrigatórias

| Validação | Evidência exigida | Resultado esperado |
|---|---|---|
| Commit da `main` resolvido | SHA validado no workflow | Verde |
| CI principal | `CI — ReqSys v2 Enterprise` com sucesso no SHA validado | Verde |
| Governança | `Governance Quality Gates` com sucesso no SHA validado | Verde |
| Governança padrão ouro | `Governança Padrão Ouro` com sucesso no SHA validado | Verde |
| Artifact auditável | Artifact contendo `evidence`, `audit` ou `report` | Verde |
| Registro de auditoria | `audit/main-post-merge-validation.json` | Verde |

## Execuções

O workflow roda em três modos:

- `push` na branch `main`;
- `workflow_dispatch` com SHA opcional;
- `schedule` horário para validar continuamente o último commit da `main`.

## Regra operacional

Nenhum merge deve ser considerado estabilizado apenas porque o PR estava verde. A estabilização só existe quando o commit resultante na `main` possui workflow associado, checks críticos verdes e artifact de auditoria publicado.

## Limitações conhecidas

- O `PR Evidence Gate` é listado como opcional na validação pós-merge porque ele é orientado a evento de PR.
- O workflow deve ser adicionado à branch protection como required check depois de estabilizado.
- Caso não haja run no SHA validado, o estado deve permanecer pendente ou bloqueado.
