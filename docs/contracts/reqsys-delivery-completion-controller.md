# ReqSys Delivery Completion Controller

## Objetivo

Executar uma avaliação horária até que o ReqSys esteja efetivamente entregue, separando:

- prontidão técnica;
- conclusão formal;
- finalização de integração;
- liberação de produção.

## Estados

| Estado | Significado |
|---|---|
| `TECHNICAL_REMEDIATION` | runtime, workflows, controles ou evidências técnicas ainda falham |
| `FORMAL_COMPLETION` | parte técnica está verde, mas atos formais reais continuam pendentes |
| `DELIVERY_FINALIZATION` | controles concluídos, aguardando integração final de PRs/workflows |
| `DELIVERED` | técnica, formalização e integração concluídas |

## Automação

A cada hora o controlador:

1. lê a matriz BACEN;
2. coleta PRs e workflows da `main`;
3. testa os endpoints públicos contratuais;
4. calcula a fase de entrega;
5. publica artifact retido por 365 dias;
6. dispara validadores report-only e não produtivos.

## Limite de autoridade

A automação não cria:

- nome de responsável pessoal;
- assinatura;
- aprovação institucional;
- atestado jurídico ou regulatório;
- evidência externa inexistente.

Esses atos são convertidos em ações humanas rastreáveis. A automação cuida da preparação, cobrança, escalonamento, evidência e bloqueio.

## Regra de produção

`production_release_allowed=true` somente no estado `DELIVERED`.

O controlador não realiza deploy e sempre publica `production_touched=false`.
