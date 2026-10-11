# Diagnóstico PC24x7 DEV antes de recuperação

O script `scripts/diagnose_pc24x7_public_dev.py` é somente leitura do runtime.
A única escrita é um arquivo novo de evidência JSON no diretório dedicado.
Não lê credenciais nem logs de aplicação. Não executa deploy ou restart.

## Execução governada
Após o bootstrap/Gateway e autorização para leitura no PC24x7, usar o SHA
corrente confirmado da main e um nome novo de evidência:

```text
python scripts/diagnose_pc24x7_public_dev.py --environment dev --expected-sha <SHA-COMPLETO-DA-MAIN> --output artifacts/pc24x7-dev-diagnostic/<CORRELATION-ID>.json
```

Esse comando físico ainda não foi executado nesta correção. CLI, contratos e
negativos foram testados isoladamente. Contexto Docker deve apontar ao pipe
local `npipe:////./pipe/dockerDesktopLinuxEngine`; overrides DOCKER_HOST ou
DOCKER_CONTEXT bloqueiam. Não mudar o contexto ou allowlists automaticamente.

A coleta exige uma API única publicada em 8210, nos projetos DEV explicitamente
permitidos; verifica novamente as identidades. Se o projeto for outro, investigar
antes de ampliar a allowlist. Somente api, frontend e nginx são inspecionados.

## Interpretação
`diagnostic_collected` significa apenas metadados coletados. Campos
`runtime_sha_verified=false` e `runtime_readiness_verified=false` impedem
interpretar o SHA esperado como versão implantada. OOM, exit code, restart count
e health auxiliam o diagnóstico; não identificam retroativamente o erro Compose
do run 38110040712.

A reconciliação agora distingue `compose_config`, `api_frontend_up` e
`nginx_up` nas falhas sensíveis, incluindo timeout/spawn. Ela continua mutativa
e requer autorização própria. Não a repetir apenas para obter um log.

O teste físico de mesma Activity e o ACK visual de Action.Submit continuam
pendentes. Este incremento não cria replay nem envia mensagem Teams.

