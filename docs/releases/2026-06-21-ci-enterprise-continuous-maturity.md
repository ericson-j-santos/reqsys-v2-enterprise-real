# Release Note — CI Enterprise Continuous Maturity

## Origem

O PR #70 introduziu em 2026-06-21 o conceito de fast path, regressão ampla, observabilidade e guardrails determinísticos.

## Estado reconciliado em 2026-10-04

A capacidade central já está presente na `main` em superfícies evoluídas:

- `CI Enterprise Fast`;
- `CI Enterprise Regression`;
- `CI Observability`;
- `scripts/ci_enterprise_guardrails.py`;
- Pre-PR Readiness;
- Governed Merge Queue e política de workflows do SHA atual.

A reconciliação não restaura versões antigas desses arquivos.

## Conteúdo preservado

- decisão arquitetural de CI em camadas;
- política de causa raiz para falhas recorrentes;
- separação entre fast path e regressão completa;
- observabilidade operacional;
- guardrails determinísticos;
- proteção contra evidência/merge em SHA obsoleto.

## Conteúdo excluído da recuperação

Commits históricos do #70 ligados a login demo, UI operacional e guardrails de segurança paralelos foram classificados como escopo contaminante e não são reaplicados.

## Validação

O contrato preventivo `tests/test_ci_enterprise_continuous_maturity_contract.py` verifica a existência e o wiring das superfícies canônicas atuais.
