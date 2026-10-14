# ReqSys #2546 — DEV deploy-check governado e somente leitura

## Origem e autorização

Issue ReqSys #2546 / incidente #1532. Tarefa persistida `cwp-cdb85c31e3cc4e972f3094ab`, request `4f6f18810783cdc6872f04f1`. A avaliação original de hotfix ocorreu no Agent Increment Gate do run #38297033941. A evidência pertence ao SHA histórico; `READY_FOR_PR` precisa ser refeito no SHA atualizado.

## Contrato de execução tipada

- O comando do proprietário `/reqsys run pc24x7-dev-deploy-check` é exato, exclusivo da issue #1705 e não aceita host, URL, token, SHA ou task_id informados no comentário.
- O workflow DEV existente executa apenas `scripts/dev_runtime_recovery.py deploy-check --expected-sha=<github.sha>`, no Desktop `DESKTOP-PDQK954`, pelo `SESSION_LAUNCH_OK` e Command Gateway com preflight do runner e worktree isolado.
- Em caso positivo, exigir identidade real do runtime, SHA completo igual ao commit de execução, Compose DEV, readiness e SELECT 1; publicar evidência sanitizada com SHA, correlation_id, task_id, host e controle de ausência de mutação.
- Em erro de SHA, banco indisponível, runner errado, comando não allowlisted, duplicidade ou evidência ausente, bloquear e registrar código sanitizado quando a sessão permitir. Não usar resultado 2xx ou `skipped` como prova.
- Não executar reinício, deploy, Docker Compose up/down, claim, requeue, rotação de segredos, HML/STG/PROD ou mutação do banco vivo.

## Aceite e dívida de automação

Pre-PR no HEAD exato, testes positivos/negativos/idempotência e CI de PR em HEAD atual; merge somente governado e revalidado. Após integração, emitir um comando literal único e conferir artefato físico, digest, CRC e leitura independente. Não marcar #2546 `CONCLUÍDO` sem execução real da tarefa por Builder e Validator.

O `NativeOneShotExecutor` integrado ao `engineering-worker-pool/main@b68e60e62ab8676a390f4ba46b256c85c4a7645b` fornece a coordenação, mas não instala handlers de produto. A instalação do Worker Pool 1.4 ativo, o adaptador efetivo do Builder/Validator e o cutover DEV ainda têm gates separados. Esta PR entrega o primeiro comando de diagnóstico de produto e NÃO consome artificialmente a tarefa da fila.
