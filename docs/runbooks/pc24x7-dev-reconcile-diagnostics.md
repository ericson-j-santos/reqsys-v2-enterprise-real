# Diagnóstico PC24x7 DEV antes de recuperação

O script `scripts/diagnose_pc24x7_public_dev.py` é somente leitura do runtime.
O modo `--stdout-only` emite somente JSON em stdout, sem arquivo de evidência.
O modo alternativo `--output` grava um arquivo novo no diretório dedicado e
exige contrato de escrita apropriado; não deve ser usado como leitura risco 1.
Não lê credenciais nem logs de aplicação. Não executa deploy ou restart.

## Execução governada
Após o bootstrap/Gateway e autorização para leitura no PC24x7, usar o SHA
corrente confirmado da main. Para o contrato de leitura risco 1, usar stdout
sem redirecioná-lo para arquivo no worktree. `-B` impede escrita de bytecode:

```text
python -B scripts/diagnose_pc24x7_public_dev.py --environment dev --expected-sha <SHA-COMPLETO-DA-MAIN> --stdout-only
```

Essa variante física ainda não foi executada nesta correção. CLI, contratos e
negativos foram testados isoladamente, incluindo snapshot sem mudança e execução
subprocesso com `-B`. O sucesso do script não substitui a aprovação final do
Gateway: exigir também estado inalterado e resultado semântico aprovado.
Não afrouxar o Gateway nem remover evidência anterior para passar o controle.

Somente quando a escrita de evidência estiver autorizada pelo contrato da sessão,
substituir `--stdout-only` por
`--output artifacts/pc24x7-dev-diagnostic/<CORRELATION-ID>.json`.
As opções são mutuamente exclusivas e uma delas é obrigatória. Ambos os modos
preservam o mesmo JSON sanitizado e códigos de saída do diagnóstico.

Contexto Docker deve apontar ao pipe
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


