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

## Incremento Pareto — scanners por superfície alterada

35. `Security Specialized Scanners` deve separar alteração de código-fonte de alteração de manifesto de dependência; mudar um arquivo Python/JavaScript não deve, por si só, disparar auditoria completa de dependências.
36. `pip-audit` deve executar em pull request somente quando `requirements*.txt` ou `pyproject.toml` forem alterados; `npm audit` deve executar somente quando manifesto/lockfile Node for alterado.
37. CodeQL deve selecionar dinamicamente apenas as linguagens cuja superfície de código-fonte foi alterada no PR. A publicação SARIF permanece atômica para o conjunto selecionado.
38. SBOM deve executar em PR apenas quando dependências, container ou infraestrutura empacotável forem alterados. `push/main` e execução manual preservam o scan completo.
39. Gitleaks permanece global em todos os pull requests e falha do roteador de escopo continua impedindo summary verde.

### Critérios de aceite — scanner Pareto

- Diff apenas de Python não materializa CodeQL JavaScript/TypeScript.
- Diff apenas de JavaScript/TypeScript não materializa CodeQL Python.
- Mudança de código sem mudança de manifesto não executa `pip-audit`/`npm audit`.
- Mudança de manifesto executa a auditoria de dependência correspondente e SBOM.
- `push/main` e `workflow_dispatch` continuam selecionando Python, JavaScript/TypeScript, auditorias de dependência e SBOM.
- A publicação CodeQL valida exatamente as categorias selecionadas e rejeita categoria ausente, inesperada ou duplicada.
- `tests/test_codeql_atomic_publish_workflow.py` permanece verde.


## Incremento Pareto — divisão por domínios e primeira extração BACEN

40. O monorepo deve manter um mapa machine-readable de domínio → paths → workflows → repositório alvo em `config/repository-domain-routing.json`.
41. A quantidade de workflows ativos deve ser tratada como orçamento versionado: no baseline deste incremento são 575; qualquer crescimento ou redução exige atualização explícita do inventário e revisão.
42. O domínio BACEN deve possuir manifesto exato dos workflows `bacen-*.yml`; drift entre o manifesto e `.github/workflows` deve falhar fechado.
43. A extração deve usar strangler/shadow copy: o source permanece autoritativo até o target comprovar equivalência de inventário, contratos de evidência e CI.
44. O seed de `reqsys-ci-platform` deve permanecer fora de `.github/workflows` enquanto estiver no monorepo, evitando criar mais um workflow ativo durante a migração.
45. A validação da topologia deve ser incorporada ao `Path-Based Workflow Router Validation` existente, sem criar novo workflow de pull request.
46. Nenhum workflow BACEN pode ser removido da origem nesta etapa; remoção/delegação exige PR posterior, target protegido, equivalência verde e rollback documentado.
47. O target canônico da primeira extração é `ericson-j-santos/reqsys-governance-bacen`; o target do CI compartilhado é `ericson-j-santos/reqsys-ci-platform`.

### Critérios de aceite — divisão por domínios

- `python -m unittest tests/test_repository_domain_routing.py -v` verde.
- `python scripts/validate_repository_domain_routing.py --json` retorna `status=passed`.
- A contagem de workflows ativos permanece 575.
- O inventário BACEN contém exatamente 65 workflows.
- O diff não adiciona workflow ativo em `.github/workflows`.
- O source BACEN permanece autoritativo até evidência equivalente no target.
- O incremento não toca produção, secrets, deploy, branch protection ou permissões administrativas.


## Incremento Pareto — Engineering Control Plane CI Baseline v2

48. A métrica por PR deve usar a janela fixa quando ela contiver pelo menos 3 PRs e ampliar progressivamente somente a amostra por PR até 360 minutos; se ainda insuficiente, deve usar fallback limitado aos PRs recentes, no máximo 7 dias, consultando os commits e workflow runs por `head_sha`.
49. A ampliação da amostra por PR não pode alterar a janela fixa global usada pelas métricas históricas nem transformar amostra insuficiente em evidência válida silenciosamente; o artifact deve expor `baseline_sample_valid` e metadados da janela efetiva.
50. O artifact deve expor `rerun_rate_percent` explicitamente como proporção de workflow runs de pull request observados com `run_attempt > 1`, além dos contadores absoluto/total.
51. `Pre-PR Readiness` com `HEAD == origin/main`, `behind_by=0` e diff vazio deve retornar `not_applicable`, publicar evidência e terminar verde sem instalar dependências/testes pesados desnecessários.
52. Diff vazio não deve ser relaxado quando o SHA for diferente da base, houver branch atrasada, divergência do HEAD esperado ou qualquer alteração real; nesses casos o comportamento continua fail-closed.

### Critérios de aceite — Baseline v2

- Amostra fixa com 3+ PRs não é ampliada.
- Baixa atividade amplia progressivamente 60 → 120 → 240 → 360 minutos e para assim que atingir a meta.
- Amostra que não atingir a meta permanece marcada como inválida para baseline.
- `rerun_rate_percent` possui teste determinístico e contagem por PR.
- No-op exato da base retorna `not_applicable` e workflow verde.
- Controle negativo com diff real ou SHA diferente não pode receber `not_applicable`.
- Schema final do artifact: `1.0.5`.

53. O fallback de baixa atividade deve listar PRs recentes em ordem determinística, consultar seus commits e coletar apenas workflow runs de `pull_request` associados ao SHA, parando ao atingir 3 PRs com evidência.
54. O fallback deve falhar fechado em coleta incompleta de commits e não pode usar paginação global ilimitada de workflow runs.
55. Menos de 3 PRs no limite de 7 dias mantém `baseline_sample_valid=false`; nenhuma métrica insuficiente pode ser apresentada como baseline conclusivo.

### Critérios adicionais — fallback de PRs recentes

- O modo `recent_prs_fallback` é explicitamente registrado no artifact.
- `selected_pr_numbers` identifica a amostra usada.
- O teste determinístico prova coleta de três PRs sem varrer histórico global.

56. A duração observada de workflow rerun deve ser calculada a partir de `run_started_at` quando `run_attempt > 1`, porque o GitHub preserva `created_at` do disparo original.
57. O tempo entre a criação original e o início de uma tentativa posterior não pode ser contabilizado como minutos ativos de CI nem contaminar o Pareto de workflows.

### Critério adicional — duração de rerun

- Um rerun com `created_at=15:00`, `run_started_at=15:30` e `updated_at=15:31` contribui exatamente 1 minuto à métrica observada.
