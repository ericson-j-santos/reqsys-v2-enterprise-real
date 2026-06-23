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
| Registro de auditoria atual | `audit/main-post-merge-validation.json` publicado pelo próprio workflow | Verde |
| Artifact auditável anterior | Artifact contendo `evidence`, `audit` ou `report`, quando já existir para o SHA | Warning controlado no bootstrap |

## Execuções

O workflow roda em três modos:

- `push` na branch `main`;
- `workflow_dispatch` com SHA opcional;
- `schedule` horário para validar continuamente o último commit da `main`.

## Regra operacional

Nenhum merge deve ser considerado estabilizado apenas porque o PR estava verde. A estabilização só existe quando o commit resultante na `main` possui workflow associado, checks críticos verdes e artifact de auditoria publicado.

## Bootstrap-aware validation

Quando ainda não existe artifact anterior para o SHA validado, o workflow deve tratar esse cenário como `bootstrap_aware=true` e registrar `warning`, sem falhar o gate por esse motivo isolado.

Isso evita falso vermelho no primeiro ciclo pós-merge, porque o artifact atual é publicado depois da avaliação inicial do próprio workflow.

## Limitações conhecidas

- O `PR Evidence Gate` é listado como opcional na validação pós-merge porque ele é orientado a evento de PR.
- O workflow deve ser adicionado à branch protection como required check depois de estabilizado.
- Caso não haja run no SHA validado, o estado deve permanecer pendente ou bloqueado.
- Falhas reais ou ausência de workflows obrigatórios continuam bloqueando a estabilização.
