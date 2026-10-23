# Golden Test compatível com Mutmut 3.8 — Requisitos

## Objetivo

Restaurar a execução determinística do workflow `Golden Test Advanced` após a
remoção, no Mutmut 3, dos argumentos legados usados diretamente na linha de
comando.

## Requisitos

1. O workflow deve instalar uma versão explícita do Mutmut para evitar drift de CLI.
2. A execução deve usar `mutmut run` sem os argumentos removidos `--paths-to-mutate`, `--tests-dir` e `--runner`.
3. A configuração versionada deve limitar as fontes a `backend/app` e as mutações a `backend/app/core/*`.
4. A seleção de testes deve permanecer em `backend/tests` por meio da configuração suportada pelo Mutmut 3.
5. Um teste de contrato deve falhar se a versão deixar de ser fixada, se os argumentos legados voltarem ou se o escopo configurado mudar.
6. O ajuste não deve executar deploy, alterar ambientes, acessar segredos ou realizar merge.

## Critérios de aceite

- `tests/test_golden_test_advanced_contract.py` passa integralmente.
- O carregador de configuração do Mutmut 3.8.0 reconhece `source_paths`, `only_mutate` e `pytest_add_cli_args_test_selection`.
- O Pre-PR Readiness admite o SHA final sem bloqueio `SDD_SPEC_REQUIRED`.
- O workflow `Golden Test Advanced` conclui com sucesso no GitHub Actions para o SHA final.
