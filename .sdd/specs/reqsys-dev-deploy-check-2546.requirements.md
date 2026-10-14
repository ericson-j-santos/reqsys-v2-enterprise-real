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

## Continuidade do bloqueio físico — 14/10/2026

No run físico #38599160248, a CLI retornou `runtime_dependency_missing` em DEV. O módulo versionado `scripts/probe_pc24x7_dev_runtime_identity.py` existe no SHA integrado, mas o nome exato que falhou e o `sys.path` do interpretador físico não foram atestados. A correção deve eliminar a dependência de importação por nome no modo CLI, carregando exclusivamente o arquivo irmão do worktree validado, sem ampliar `PYTHONPATH` nem a allowlist do Gateway. O caminho importado como pacote durante testes continua compatível. Fonte ausente, loader inválido e contrato incompleto falham com códigos tipados e sem revelar caminhos. Validar positivo, negativo, sombreamento de módulo, repetição, regressão, CI e readback após merge. Novo teste físico somente após mudança material comprovada; sem deploy/restart/cutover ou consumo das tasks #2546/#2547.


## Fixação do interpretador após a PR #2592

12. O subprocesso governado deve receber o caminho absoluto de `REQSYS_PYTHON`, já preparado e validado pelo workflow, em vez de resolver `python` por PATH ou cwd.
13. O teste hospedado em Windows deve usar o ZIP embeddable 3.12.10 com hash fixado e seu `python312._pth` real para comprovar: carga do probe irmão sem PYTHONPATH, falha fechada quando o arquivo irmão não existe e aceitação do caminho absoluto pela política/Gateway fixados.
14. Nenhuma allowlist, permissão, deploy, instalação no host físico ou despacho DEV adicional integra esta correção.

## Diagnóstico diferenciado de prontidão — 14/10/2026

O run físico #38608094816, com as correções de importação e Python pinado integradas no SHA `8e6c7858a8509262092efe4b884d732eb5a9c39c`, ainda retornou `deploy_readiness_timeout`. O artifact `11915947726` foi verificado por SHA-256 e CRC, e confirma banco/SHA runtime não verificados. A função `wait_live` absorve erros de identidade/Compose, disponibilidade e SHA diferente antes de emitir esse timeout, impedindo identificar a causa física.

15. Preservar `wait_live` genérico utilizado em rollback; ativar códigos diferenciados **somente** no modo `deploy-check`, sem mudanças físicas.
16. Classificar somente códigos fixos e sanitizados em `deploy_readiness_sha_mismatch`, `deploy_readiness_probe_unavailable`, `deploy_readiness_unhealthy`, `deploy_readiness_container_unavailable`, `deploy_readiness_scope_invalid`, `deploy_readiness_probe_invalid` ou `deploy_readiness_unknown`. Nunca refletir conteúdo de exceções, URLs, caminhos nem secrets.
17. Falha de escopo ou contrato local é não recuperável dentro desta execução e deve falhar imediatamente. Falha transitória de probe e SHA divergente preservam tentativa limitada; retorno ao SHA correto permite sucesso.
18. Regressões devem comprovar cada família de erro, controle negativo, sigilo, recuperação transitória, timeout bounded, não mutação e contrato do recibo. O CI precisa executar esses testes. Após merge e verificação de SHA, apenas uma nova leitura física autorizada; não inferir recuperação pelo CI.
