# Environment Promotion History

## Objetivo

Persistir as decisões produzidas pelo `Environment Promotion Readiness Gate` e determinar, com evidência observada, quando o ambiente STG pode ser candidato a enforcement bloqueante.

## Contrato

Artifact: `environment-promotion-history/history.json`.

Campos principais:

- `point_count`: total de decisões preservadas;
- `points`: janela histórica limitada às 180 decisões mais recentes;
- `stg_enforcement_maturity.observed_window`: execuções STG consideradas;
- `stg_enforcement_maturity.criteria_met`: critérios técnicos atingidos;
- `stg_enforcement_maturity.next_action`: próximo passo governado.

## Critério de maturidade STG

A maturidade técnica exige as cinco execuções STG mais recentes:

1. todas válidas (`approved` ou `approved_with_warning`);
2. pelo menos quatro decisões `approved`;
3. nenhuma decisão `blocked` ou `insufficient_evidence`.

Atingir o critério não altera automaticamente o enforcement. O resultado é `ready_for_human_approval`, preservando aprovação humana antes de tornar STG bloqueante.

## Guardrails

- atualização idempotente por ambiente, run ID, SHA e data da decisão;
- DEV e PROD não contaminam a janela de maturidade STG;
- retenção máxima de 180 pontos;
- nenhuma promoção, deploy ou alteração de branch protection;
- ausência ou falha do gate de origem não gera histórico válido;
- `automatic_change_allowed` permanece `false`.

## Próximo incremento condicionado

Após cinco execuções STG válidas e aprovação humana explícita, alterar o gate de promoção para tornar STG bloqueante. Até lá, o workflow permanece apenas como coletor e avaliador de maturidade.
