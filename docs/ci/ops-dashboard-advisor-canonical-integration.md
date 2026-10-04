# Executive Promotion Advisor no Ops Dashboard canônico

## Objetivo

Garantir que o artifact principal `ops-dashboard-static` publique o card do Executive Promotion Advisor e o respectivo contrato no Runtime Executive Index.

## Integração

O passo canônico `Inject Workflow Efficiency visual card`, já executado pelo workflow `Ops Dashboard`, passa a:

1. procurar evidência consolidada do Advisor;
2. preservar evidência já existente no Runtime Executive Index;
3. aplicar fallback `REVIEW` seguro quando a evidência ainda não estiver disponível;
4. forçar `mode=report-only`;
5. forçar `production_blocker=false`;
6. manter `human_approval_required=true`;
7. injetar o card visual de forma idempotente;
8. validar HTML e contrato antes do empacotamento.

## Precedência

1. card já consolidado no Runtime Executive Index;
2. artifact `executive-promotion-advisor-state`;
3. artifact `executive-promotion-advisor`;
4. fallback seguro `REVIEW`.

## Guardrails

- nenhuma chamada externa no navegador;
- nenhuma promoção automática;
- nenhuma alteração em deploy, merge queue, auto-merge ou branch protection;
- falha de evidência resulta em `REVIEW`, nunca em `READY` implícito;
- aprovação humana permanece obrigatória.

## Evidência

O próprio `ops-dashboard-static` passa a conter:

- `index.html` com o card do Advisor;
- `data/runtime-executive-index.json` com `cards.executive_promotion_advisor`;
- guardrails explícitos de report-only e Human Gate.
