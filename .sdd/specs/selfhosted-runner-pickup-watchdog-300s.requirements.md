# Self-hosted runner pickup watchdog — 300 segundos

## Problema

O ReqSys Authorized Actions Gateway cancelava workflows self-hosted ainda em fila após 36 sondagens de 5 segundos (180 segundos). O comportamento fazia o restore DEV do Worker Pool ser cancelado antes do limite canônico de 300 segundos definido pelo progress watchdog.

## Requisito

1. O gateway deve conceder até 300 segundos para aquisição de um run self-hosted.
2. O intervalo de sondagem permanece em 5 segundos.
3. Estados `pending`, `queued`, `requested` e `waiting` não contam como pickup.
4. Se o run permanecer sem pickup após 300 segundos, o gateway deve continuar falhando fechado com `SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY` e cancelar o run sem worker.
5. Runs que avancem para execução antes do limite não devem ser cancelados pelo cleanup de pickup.
6. A mudança não toca produção, deploy, segredos nem permissões administrativas.

## Evidência observada

- restore Worker Pool run `35942469237`: cancelado sem runner/steps após aproximadamente 180 segundos;
- restore Worker Pool run `35942728217`: mesmo padrão;
- workflow vigente continha `seq 1 36` com `sleep 5`.

## Critérios de aceite

- teste de contrato exige timeout de 300 segundos e polling de 5 segundos;
- teste impede regressão para `seq 1 36`;
- suíte relevante e gates da PR ficam verdes no mesmo HEAD;
- restore subsequente deve receber pickup ou terminar somente após o novo limite, preservando evidência explícita.

## Rollback

Reverter o commit se houver evidência de efeito adverso objetivo. Não reduzir novamente o timeout abaixo do contrato canônico sem alteração correspondente na regra de projeto.
