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
