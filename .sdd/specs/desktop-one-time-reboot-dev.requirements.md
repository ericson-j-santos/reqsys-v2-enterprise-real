# Desktop one-time reboot DEV — desbloqueio governado

## Objetivo

Permitir uma única reinicialização remota de `DESKTOP-PDQK954` em DEV quando houver autorização explícita do owner no chat atual e o reboot for a precondição necessária para restaurar o bootstrap estável do Runtime Platform.

## Contrato

1. A entrada operacional é somente o comando exato `/reqsys run desktop-one-time-reboot-dev` na issue operacional #1705, criado pelo owner.
2. O workflow executa somente no runner Noteri allowlisted.
3. O alvo é constante: `DESKTOP-PDQK954`; não existem inputs para host, comando, operação ou ambiente.
4. A implementação usa exclusivamente `chatgpt-operational-rules/scripts/owner_remote_host_power_once.py` no SHA pinado.
5. A autorização local dura no máximo 10 minutos, é consumida antes da submissão e é vinculada a action_id, executor e alvo.
6. O reboot usa atraso de 30 segundos, sem force, shutdown ou poweroff.
7. Um segundo execute deve falhar, comprovando anti-replay.
8. A autorização local é revogada antes do fim do job.
9. O artifact registra SHA ReqSys, SHA das regras, correlation_id, alvo e controles, sem segredo.
10. Um run verde comprova apenas submissão do reboot; conclusão funcional exige evidência independente pós-reboot.
11. Após o host retornar, validar `:8787`, capability `host.github_runner.bootstrap.v1`, listener, pickup GitHub e E2E do Modo Estudo no SHA corrente.
12. Sem produção, deploy, leitura de segredo, shell arbitrário, alteração de RBAC ou alvo arbitrário.

## Critérios de aceite

- O comando de gateway é exato e não aceita host, operação, action_id ou comando fornecido pelo chamador.
- O modo `reboot-once` executa somente no Noteri e fixa `DESKTOP-PDQK954` em DEV.
- A autorização é consumida antes da submissão, replay é bloqueado e a autorização é revogada.
- Sucesso do workflow comprova somente submissão; a recuperação exige leitura independente pós-reboot.
- O fluxo posterior exige `:8787`, capability de bootstrap, listener, pickup GitHub e E2E do Modo Estudo no SHA corrente.

## Evidência terminal

A frente só pode avançar para `concluído` depois de prova pós-reboot no estado atual: Runtime Orchestrator correto, runner com pickup real e E2E `NORMAL -> ESTUDO -> replay -> NORMAL` com leitura independente.
