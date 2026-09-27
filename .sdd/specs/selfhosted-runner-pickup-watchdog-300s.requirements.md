# Self-hosted runner pickup watchdog — 300 segundos (superseded)

## Status

Este contrato histórico foi superseded em 2026-09-24 pela PR #2070, que reduziu a janela de pickup do Authorized Actions Gateway para 60 segundos. O arquivo é preservado para rastreabilidade e não define mais o timeout vigente.

O contrato ativo permanece fail-closed em 60 segundos, mas pickup deve ser comprovado por evidência material do job self-hosted. Um job com `started_at` e label `self-hosted` conta como adquirido mesmo quando o status agregado do workflow run ainda estiver atrasado em `queued`.

## Contexto histórico

O contrato original elevou 180 segundos para 300 segundos porque workflows self-hosted eram cancelados prematuramente. Posteriormente a PR #2070 reduziu o limite para 60 segundos por requisito de fail-fast.

A execução real `36346013726` em 2026-09-27 demonstrou um caso diferente: o runner `Noteri` iniciou o job antes do limite, mas o status agregado consultado pelo gateway permaneceu `queued`; o gateway então cancelou uma execução que já tinha pickup físico.

## Contrato vigente

1. Janela de pickup: 60 segundos.
2. Polling: 5 segundos.
3. Evidência preferencial: job com `started_at != null` e label `self-hosted`.
4. Status agregado do run continua como fallback de observação.
5. Somente ausência de evidência material até o limite produz `SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY`.
6. Cleanup/cancelamento permanece fail-closed somente para run sem pickup comprovado.
7. Produção, deploy, segredos e permissões administrativas não são tocados.

## Evidência

- gateway run `36346007603`;
- target run `36346013726`;
- runner `Noteri` iniciou o job por volta de `2026-09-27T19:54:30Z`;
- o gateway ainda registrou `runner_pickup_status=queued` e cancelou o target, comprovando atraso do status agregado.

## Critérios de aceite

- teste de contrato preserva 60 segundos e polling de 5 segundos;
- teste exige consulta ao endpoint de jobs e prova por `started_at` + label `self-hosted`;
- run com job iniciado não pode ser cancelado apenas porque o status agregado ainda aparece como `queued`;
- run sem qualquer pickup continua sendo cancelado após o limite.
