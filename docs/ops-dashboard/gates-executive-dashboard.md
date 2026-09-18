# ReqSys Gates Executive Dashboard

> Atualização: 2026-06-30 21:30 BRT  
> Escopo: painel executivo estático para gates operacionais recém-consolidados.

## Decisão Executiva

🟢 **Continuar incrementos pequenos e independentes.**

O lote de gates operacionais está consolidado com semáforo verde para continuidade controlada. A recomendação é manter paralelismo apenas onde não houver sobreposição de arquivos, alteração de contrato público, workflow crítico ou runtime backend/frontend compartilhado.

## Indicadores

| Indicador | Valor | Cor | Decisão |
| --- | ---: | --- | --- |
| Gates consolidados | 5 | 🟢 Verde | Continuar |
| Gates amarelos | 0 | 🟢 Verde | Sem atenção imediata |
| Gates vermelhos | 0 | 🟢 Verde | Sem bloqueio |
| Capacidade recomendada | até 5 PRs documentais/baixo risco | 🟢 Verde | Permitido com preflight |
| Impacto runtime | 0 | 🟢 Verde | Seguro |

## Cards Executivos

| Gate | Status | Score | Próxima ação |
| --- | --- | ---: | --- |
| Capacidade de PR Paralelo | 🟢 Verde | 100 | Permitir PRs documentais e incrementos de baixo risco. |
| CI Green Release Gate | 🟢 Verde | 100 | Tratar `ready_green` como pronto para merge. |
| Guardrails de Escrita em Produção | 🟢 Verde | 100 | Manter `read-first` e aprovação para escrita em produção. |
| Contrato de Evidência por Correlation ID | 🟢 Verde | 100 | Propagar `correlation_id` em logs, artifacts e relatórios. |
| Conflict Preflight Check | 🟢 Verde | 100 | Comparar arquivos alterados antes de abrir novo PR. |

## Regras de Continuidade

1. Continuar apenas com branches criadas da `main` atualizada.
2. Evitar paralelismo em `.github/workflows/**`, `backend/app/**`, `frontend/src/router/**` e contratos públicos.
3. Permitir até 5 PRs paralelos somente para documentação, dados estáticos ou checks isolados.
4. Reduzir para até 3 PRs quando houver testes ou views frontend independentes.
5. Serializar qualquer alteração em runtime, API, deploy, autenticação ou workflow crítico.

## Próxima Sequência Recomendada

1. Validar CI do PR funcional de automação de PR paralelo.
2. Usar este dashboard como referência executiva dos gates.
3. Fechar PRs antigos/obsoletos após confirmar estado e ausência de utilidade.
4. Atacar o PR #622 apenas depois de reduzir ruído operacional.

## Rollback

Remover este documento e `docs/ops-dashboard/data/gates-executive-dashboard.json`.
