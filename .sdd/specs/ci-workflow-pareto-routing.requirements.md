# Requisitos — Roteamento Pareto de workflows de CI

## Objetivo

Reduzir fan-out e contenção de runners em pull requests sem remover checks protegidos, sem reduzir secret scanning e sem substituir validações determinísticas por heurísticas.

## Requisitos funcionais

1. Workflows listados em `protected_workflows` devem permanecer materializáveis em todo PR aplicável e não podem receber filtros de path que impeçam o contexto obrigatório.
2. `Security Specialized Scanners` deve manter Gitleaks em todos os PRs; pip-audit, npm audit, SBOM e CodeQL podem ser condicionados à superfície alterada.
3. Falha do roteador de segurança deve falhar fechado e nunca produzir summary verde.
4. `PR Scope Labeler` deve produzir apenas snapshot inicial no evento `opened`; classificação contínua fica centralizada em `PR Fast Classifier`.
5. `PR Fast Classifier` não deve rerodar em eventos `labeled` ou `unlabeled`.
6. `Preview Environment Contract` deve autoexecutar somente quando houver mudança de runtime, empacotamento ou no próprio workflow; execução manual permanece disponível.
7. `Runtime Risk Scoring`, `PR Quality Review` e `Predictive Regression Guard` são advisory/report-only e não devem autoexecutar para PR apenas de workflow, testes ou documentação.
8. O validador `validate_path_based_workflow_router.py` deve verificar tanto os paths mínimos esperados quanto a ausência de rotas advisory amplas já removidas.
9. Referências a frontends legados `frontend-angular` e `frontend-vuetify` não podem ser reintroduzidas em workflows operacionais.
10. Mudanças deste incremento não podem tocar produção, secrets, permissões administrativas, deploy ou branch protection.

## Critérios de aceite

- `scripts/check_legacy_frontend_references.py` sem referências legadas.
- `scripts/validate_path_based_workflow_router.py` aprovado.
- `tests/test_codeql_atomic_publish_workflow.py` verde.
- `tests/test_report_only_workflow_pareto.py` verde.
- Pre-PR Readiness sem `SDD_SPEC_REQUIRED`.
- HEAD do PR sincronizado com `main`, sem conflito.
- Os checks protegidos continuam presentes.
- Para um novo `synchronize` desta PR, `PR Scope Labeler`, `Runtime Risk Scoring`, `PR Quality Review` e `Predictive Regression Guard` não materializam quando o diff não cruza suas superfícies.

## Evidência

Registrar HEAD, base SHA, quantidade de workflows materializados, workflows evitados, resultados dos gates e eventual fila observada.

## Rollback

Reverter apenas os commits deste incremento de roteamento. Não há efeito em runtime ou produção.

## Incremento Pareto — fan-out do watcher e auditoria total

11. O `PR CI Watch` deve usar apenas `CI Enterprise Fast` e `CI — ReqSys v2 Enterprise` como produtores automáticos de `workflow_run`; gates auxiliares continuam sendo lidos como evidência, mas não devem gerar novas execuções do watcher.
12. Execuções obsoletas do `PR CI Watch` para o mesmo PR devem ser canceladas quando chegar novo sinal ou novo SHA.
13. `Workflow Governance Consolidator` deve inventariar todos os workflows presentes no SHA e separar `pull_request`, PR com/sem `paths`, `workflow_run`, fan-out alto, `schedule` e `workflow_dispatch` isolado.

### Critérios de aceite adicionais

- `PR CI Watch` possui exatamente dois produtores canônicos de `workflow_run` e `cancel-in-progress: true`.
- Os cinco produtores auxiliares removidos do watcher permanecem disponíveis como gates independentes; nenhum gate protegido é excluído.
- `Workflow Governance Consolidator` publica `execution_surface` para o inventário completo e não classifica `PR CI Watch` como fan-out alto.
- Testes focados de Pareto e consolidação ficam verdes no HEAD exato.

## Incremento Pareto — gates específicos de domínio

14. Gates específicos de domínio devem usar filtro de `pull_request.paths` quando sua decisão depende de arquivos versionados específicos e imutáveis fora daquele domínio.
15. `BACEN Production Formal Gate` deve materializar em PR somente quando matriz/reconciliação, validador, teste, workflow ou contrato de SHA requerido forem alterados.
16. `Enterprise Runtime Governance Gates` deve materializar em PR somente quando houver mudança em runtime/config/infra produtivos ou no próprio contrato do gate; o `push main` completo permanece inalterado.
17. `Minimum Controlled Version Gate` deve materializar em PR somente quando manifesto, validador, testes ou o próprio workflow forem alterados.
18. `Guard Rail — Base de probes descartáveis` deve materializar em PR apenas para alteração de workflows ou de seu validador/teste.
19. `PR Governed CI Validation` não deve rerodar por mudança de label, pois o SHA validado não mudou.

### Critérios de aceite adicionais

- PR sem alteração BACEN não materializa `BACEN Production Formal Gate`.
- PR sem alteração de runtime/config/infra não materializa `Enterprise Runtime Governance Gates`.
- PR sem alteração do contrato de versão mínima não materializa `Minimum Controlled Version Gate`.
- PR sem alteração de workflows/probe não materializa `Guard Rail — Base de probes descartáveis`.
- Evento de label não dispara `PR Governed CI Validation`.

20. `Test Quality Gate — Padrão Ouro` não deve usar wildcard global de workflows; deve reagir apenas aos workflows que alteram execução/cobertura de testes.
21. `PR Governed CI Validation` deve materializar automaticamente apenas quando os contratos de CI que ele próprio valida forem alterados; execução manual permanece disponível.

### Critérios de aceite — autoauditorias de CI

- Alteração em workflow não relacionado a testes não materializa `Test Quality Gate — Padrão Ouro`.
- PR sem alteração em `ci.yml`, `ci-security.yml`, `ci-e2e-governado.yml`, `ci-observability.yml`, seletor backend ou estratégia de aceleração não materializa `PR Governed CI Validation`.

22. `Requirement Lifecycle Evidence` não deve rerodar em `synchronize`, pois a evidência de PR usa referência estável por número/título/body/head-ref; o commit de merge permanece coberto por `closed`.

### Critério de aceite — lifecycle

- Novo SHA em PR existente não materializa `Requirement Lifecycle Evidence`.
- `opened`, `reopened`, `closed`, `workflow_dispatch` e `workflow_call` permanecem disponíveis.

23. `Pre-PR Readiness Gate` deve usar a mesma chave de concorrência para `push` da branch e `pull_request` do mesmo PR, de modo que a execução mais nova cancele a duplicata sem remover nenhum dos dois gatilhos.

### Critério de aceite — deduplicação Pre-PR

- `push` e `pull_request` para a mesma branch resolvem para `pre-pr-readiness-<head-ref>`.
- `cancel-in-progress: true` permanece ativo.
- A cobertura antes da abertura do PR e dentro do PR é preservada sem dois runners simultâneos para o mesmo HEAD.

## Incremento Pareto — orçamento bloqueante e workflows especializados

24. O caminho crítico de pull request deve possuir orçamento explícito de no máximo 10 workflows bloqueantes, versionado em `config/ci-workflow-pareto-policy.json`.
25. O orçamento deve ser validado dentro de `CI — ReqSys v2 Enterprise`, sem criar um workflow adicional apenas para o budget guard.
26. `ReqSys 360 Coherence Gate` não deve executar em PR por alterações genéricas de backend, runtime, services ou frontend; em PR deve reagir somente às superfícies de navegação/ReqSys 360, mantendo a cobertura ampla em `push/main`.
27. `Trilha D — Qualidade e Governança` não deve executar em todo PR de backend; os gatilhos de contrato permanecem no PR e a validação ampla de backend permanece em `push/main`.
28. `Kindle Knowledge Local Cache` deve executar somente o contrato estático em pull request. Qualquer job físico em Noteri/Desktop deve falhar fechado quando `github.event_name == 'pull_request'` e permanecer disponível em `push/main`, `schedule` e `workflow_dispatch`.
29. A política deve falhar quando um workflow protegido também for classificado como report-only ou quando a quantidade de workflows protegidos exceder o orçamento.
30. O cenário de regressão deve usar como fixture os 15 arquivos reais da PR #1954 e comprovar deterministicamente que ReqSys 360, Trilha D e Kindle não seriam selecionados como workflows especializados de PR.

### Critérios de aceite — CI Budget Guard

- `tests/test_ci_budget_guard.py` verde, incluindo os controles negativos.
- `blocking_workflow_budget=10` e `blocking_workflow_count <= 10`.
- A fixture da PR #1954 resulta em `specialized_candidates_for_diff=[]`.
- `backend-lint`, `backend-test` e `frontend-build` dependem do `ci-budget-guard`, impedindo CI caro quando o contrato de orçamento falha.
- O job de governança final também depende do budget guard.
- Nenhum gate em `protected_workflows` é removido.
- O E2E físico Kindle não executa em PR; a rede de segurança pós-merge continua materializável.
- Repetir a avaliação com a mesma entrada gera a mesma decisão.

## Incremento Pareto — consolidação report-only pós-CI

31. Workflows consultivos não devem competir com os gates bloqueantes durante `pull_request`. `Runtime Risk Scoring`, `PR Quality Review`, `Predictive Regression Guard`, `Preview Environment Contract` e `PR Fast Classifier` devem permanecer disponíveis via `workflow_dispatch`, mas sem gatilho direto de PR.
32. Um único `CI Advisory Router` deve consumir a conclusão bem-sucedida de `CI — ReqSys v2 Enterprise`, resolver o PR pelo SHA e registrar quais diagnósticos consultivos são aplicáveis.
33. O `CI Advisory Router` é estritamente report-only: não pode possuir `actions: write`, não deve disparar workflows automaticamente, não pode bloquear merge e não toca produção.
34. `Deep Governance Review` deve materializar em PR somente no evento `labeled`; novos SHAs não devem criar execuções vazias via `synchronize`.

### Critérios de aceite — report-only fora do caminho crítico

- Os cinco workflows consultivos não contêm `pull_request:` em seu bloco de gatilho.
- Todos os cinco preservam `workflow_dispatch:`.
- `CI Advisory Router` possui `workflow_run` para `CI — ReqSys v2 Enterprise` com `types: [completed]`.
- A execução automática do router só aceita fonte `pull_request` concluída com `success`.
- O artifact consolidado declara `automatic_dispatch=false`, `critical_path_blocker=false` e `production_touched=false`.
- `Deep Governance Review` contém `types: [labeled]` e não contém `synchronize` no trigger.
- `scripts/validate_path_based_workflow_router.py` e `tests/test_report_only_workflow_pareto.py` ficam verdes.

