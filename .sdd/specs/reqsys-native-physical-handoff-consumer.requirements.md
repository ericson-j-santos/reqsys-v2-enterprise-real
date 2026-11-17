# Consumidor de prova física execution-bound — ReqSys DEV

## Critérios de aceite

1. Consumir exclusivamente E2E Platform no SHA integral `29278bbf9e84f851edbe66cd36ef0ca924521f7b` e validar o hash do CLI oficial antes da execução.
2. Contexto de repositório, PR, HEAD, ambiente, run, job e attempt vem do controlador confiável, nunca do artifact.
3. Aceitar somente recibo Ed25519 válido, contemporâneo, não sintético, com dois hosts físicos distintos, mesma tarefa, Session Launcher/Gateway, runner, lease/worktree, CAS, interrupção, retomada, readback, replay negativo e custo zero.
4. Ausência, SHA/hash divergente, campo faltante, artifact antigo/sintético, host único, resultado inválido ou tentativa divergente falha fechado.
5. Validação física bem-sucedida pode produzir `native_physical_admitted=true`, mas nunca `dispatch_allowed`, `merge_authorized` ou `deployment_authorized`.
6. Este incremento não executa hosts, aplica labels, lê secrets, altera Docker, HML/STG/PROD, faz merge ou deploy.
