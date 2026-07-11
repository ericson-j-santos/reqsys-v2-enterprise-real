# Executive Promotion Advisor no Ops Dashboard

## Objetivo

Expor visualmente a recomendação do Executive Promotion Advisor no Ops Dashboard e validar o card no artifact empacotado, sem alterar promoção, deploy ou branch protection.

## Fonte canônica

O card consome apenas `cards.executive_promotion_advisor` de `runtime-executive-index.json`.

## Conteúdo visual

- decisão `READY`, `REVIEW` ou `HOLD`;
- confiança percentual;
- quantidade de domínios de risco;
- exigência de aprovação humana;
- recomendação executiva.

## Guardrails

- `mode=report-only`;
- `production_blocker=false`;
- `human_approval_required=true`;
- nenhuma chamada externa;
- nenhum cálculo de promoção no navegador;
- nenhuma alteração automática de deploy, merge queue, auto-merge ou branch protection.

## Evidência

O workflow `Executive Promotion Advisor Dashboard` publica o artifact `executive-promotion-advisor-dashboard-smoke`, contendo `evidence.json` com validação do HTML e do contrato empacotado.

## Próximo passo

Após a integração ao workflow principal do Ops Dashboard, executar smoke na URL pública implantada e registrar a evidência por ambiente.
