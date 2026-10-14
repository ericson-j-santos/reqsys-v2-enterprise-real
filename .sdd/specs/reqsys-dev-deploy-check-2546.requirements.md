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

## Critérios de aceite

1. O comentário aceito deve corresponder exatamente ao comando fixo do owner na issue #1705; mensagem indevida e replay dentro da janela devem ser rejeitados.
2. O checkout, o Session Launcher e o Command Gateway devem confirmar host DEV, sessão íntegra e `github.sha` corrente antes de executar somente `deploy-check`.
3. O resultado positivo requer `runtime_sha` exato, ambiente DEV, contêineres válidos e `SELECT 1` aprovado; ausência ou divergência gera resultado bloqueado, nunca verde.
4. A execução deve produzir recibo sanitizado e evidência independente, incluindo erros categorizados quando o Gateway chegou a executar.
5. Nunca efetuar restart, deploy, claim/requeue, alteração de banco vivo, exposição de segredo ou ação em HML/STG/PROD.
6. Antes da PR: `READY_FOR_PR=passed` no HEAD final. Após o merge: teste físico no SHA integrado e readback independente; a task só encerra após Builder/Validator reais.

## Diagnóstico posterior ao ensaio físico #38577878951

O Gateway executou a operação somente leitura no SHA `faf9e995337bc2c28ee5b0b8bb30ce8545e5d3c1`, mas o subprocesso retornou código 1 sem emitir JSON. O recibo sanitizado `11901346670` classificou o resultado como `inner_result_missing`; a causa física permanece indeterminada.

### Critérios adicionais — saída JSON em erros esperados

7. Apenas no modo `deploy-check`, exceções conhecidas de arquivo, permissão, importação, OSError, timeout e payload malformado devem ser convertidas em códigos de categoria fixa, sem mensagens, paths ou traceback.
8. Preservar os modos de captura, preparação, validação e rollback e não suprimir seus erros por este incremento.
9. O parser público deve reconhecer as seis novas categorias exatas, mantendo `FAILED` para erro comprovado e `UNVERIFIED` quando não houver envelope consistente.
10. Testar cenários positivos, negativos, timeout, idempotência e regressão, e cumprir Pre-PR/CI/GMQ no SHA final. Um novo E2E físico só pode ser acionado após uma alteração material integrada.
11. Nenhum restart, deploy, alteração do SQLite ativo, segredo, claim, requeue, HML/STG ou PROD faz parte desta correção.
