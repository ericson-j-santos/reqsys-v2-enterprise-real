# CI Enterprise Continuous Maturity

## Objetivo

Consolidar o objetivo original do PR #70 sobre as superfícies atuais da `main`, sem restaurar workflows, UI ou scanners históricos que foram substituídos ou estão fora do escopo.

## Requisitos

1. `CI Enterprise Fast` deve existir e continuar usando admission controller e guardrails determinísticos.
2. `CI Enterprise Fast` deve permanecer workflow obrigatório na política do SHA atual.
3. `CI — ReqSys v2 Enterprise` e `Pre-PR Readiness Gate` devem continuar obrigatórios.
4. `CI Enterprise Regression` deve permanecer separado do fast path e suportar agenda/manual.
5. Etapas explicitamente report-only da regressão não podem ser tratadas como substitutas dos gates obrigatórios.
6. `CI Observability` deve ser a superfície canônica de observabilidade da esteira.
7. O workflow histórico `ci-enterprise-observability.yml` não deve ser recriado.
8. `scripts/ci_enterprise_guardrails.py` deve continuar produzindo artifacts JSON/Markdown de guardrails.
9. Alterações históricas de login, UI e segurança paralela acumuladas na branch antiga não fazem parte da recuperação.
10. Nenhum deploy, promoção de ambiente, segredo ou permissão administrativa é alterado por esta reconciliação.

## Critérios de aceite

- teste contratual preventivo verde no HEAD atual;
- SDD, segurança e governança verdes;
- branch sincronizada com a `main`;
- PR sem conflito e mergeável;
- nenhuma superfície de workflow duplicada introduzida.
