# Noteri — diagnóstico governado de heartbeat (DEV)

## Objetivo

Comprovar se o worker `noteri` mantém heartbeat válido no plano de controle existente, usando o runner ReqSys que já executou o teste isolado. A sonda é temporária, somente leitura e não autoriza recuperação ou alteração do perfil.

## Critérios de aceite

1. A execução no host `Noteri` exige SHA exato e Session Launcher com `SESSION_LAUNCH_OK` antes do Command Gateway de risco 1.
2. Um único worker com identidade esperada, autenticação e controlador válidos anuncia `host.profile.set.v1`.
3. Duas leituras independentes apresentam `last_heartbeat` crescente, mantendo `fresh=true`.
4. Host divergente, SHA divergente, worker ausente/duplicado, heartbeat imóvel ou capability ausente falham fechados.
5. O teste mantém perfil/runtime intactos, sem reboot, segredos, terminal irrestrito ou despesas adicionais.
6. CI valida os testes versionados; resultado de runner na fila ou E2E isolado não substitui E2E real do Task Console e do perfil persistente.

## Evidência

Código de origem rastreável à PR de diagnóstico do orquestrador #55; execução física em branch ReqSys isolada, com `correlation_id` por run e leitura independente do Gateway. A liberação final pertence à issue do heartbeat `reqsys-engineering-orchestrator#16`.
