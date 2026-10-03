# Executive Promotion Advisor no Estado Único

## Objetivo

Consolidar a recomendação do Executive Promotion Advisor no Runtime Executive Index e no Executive Brief, preservando a decisão global de produção.

## Contratos enriquecidos

- `runtime-executive-index.json`;
- `executive-brief.json`.

## Evidências publicadas

- decisão `READY`, `REVIEW` ou `HOLD`;
- confiança percentual;
- domínios de risco;
- recomendação executiva;
- `correlation_id`;
- exigência de aprovação humana.

## Guardrails

- `mode=report-only`;
- `production_blocker=false`;
- `human_approval_required=true`;
- nenhuma alteração em deploy, merge queue, auto-merge ou branch protection;
- nenhuma alteração automática no estado global de produção.

## Fluxo

1. O Executive Promotion Advisor gera seu artifact.
2. O workflow de consolidação baixa o artifact da execução fonte.
3. Cópias auditáveis do Estado Único e do Executive Brief são enriquecidas.
4. O artifact `executive-promotion-advisor-state` é publicado por 90 dias.
5. A promoção permanece condicionada aos gates existentes e à aprovação humana.
