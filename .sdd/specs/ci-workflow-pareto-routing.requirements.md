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
