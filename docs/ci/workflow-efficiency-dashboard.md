# Workflow Efficiency Dashboard

## Objetivo

Transformar as recomendações Pareto de workflows por PR em um contrato executivo consumível pelo Ops Dashboard, sem alterar automaticamente qualquer workflow.

## Entradas

- `docs/ops-dashboard/data/ci-workflow-pareto-recommendations.json`

## Saídas

- `docs/ops-dashboard/data/ci-workflow-efficiency-dashboard.json`
- `docs/ops-dashboard/data/history/ci-workflow-efficiency-history.json`

## Indicador executivo

`Workflow Efficiency Score` representa a proporção estimada de execuções necessárias sobre o total observado nos workflows report-only analisados.

- Verde: score maior ou igual a 85%.
- Amarelo: score entre 70% e 84,99%.
- Vermelho: score abaixo de 70%.

O score não bloqueia merge e não altera branch protection.

## Ranking Pareto

O dashboard publica os dez workflows com maior ganho potencial, contendo:

- frequência por PR;
- presença percentual;
- execuções potencialmente evitáveis;
- economia percentual potencial;
- decisão atual;
- prioridade executiva.

## Histórico

São mantidas as últimas 30 medições para cálculo de tendência e comparação temporal.

## Guardrails

- modo exclusivamente `report_only`;
- nenhuma alteração automática de workflow;
- gates obrigatórios permanecem protegidos;
- qualquer filtro real de `paths` exige PR separado;
- cada otimização futura exige evidência antes/depois e rollback definido.

## Rollback

Remover o builder, testes, workflow e esta documentação. Como o incremento não altera workflows existentes nem contratos obrigatórios, o rollback é isolado.
