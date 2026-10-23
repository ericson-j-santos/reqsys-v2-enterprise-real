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
6. Dependências locais importadas durante a coleta da suíte devem ser declaradas em `also_copy`, sem copiar o repositório inteiro para o sandbox.
7. Testes que importam o pacote operacional `scripts` devem resolver a raiz do repositório via `pythonpath`, sem substituir o pacote `app` mutado.
8. Testes estruturais que dependem de `parents[2]` devem ficar fora da coleta isolada, pois validam assets externos a `app/core` e calculam outra raiz no sandbox.
9. O teste do registro Agile deve gerar um identificador de pacote exclusivo por execução e reutilizar o mesmo payload dentro do cenário de idempotência, evitando vazamento de estado entre as fases repetidas do Mutmut.
10. O ajuste não deve executar deploy, alterar ambientes, acessar segredos ou realizar merge.

## Critérios de aceite

- `tests/test_golden_test_advanced_contract.py` passa integralmente.
- `backend/tests/test_agile_package_registry.py` passa em execuções consecutivas contra o banco de teste persistente.
- O carregador de configuração do Mutmut 3.8.0 reconhece `source_paths`, `only_mutate` e `pytest_add_cli_args_test_selection`.
- O Pre-PR Readiness admite o SHA final sem bloqueio `SDD_SPEC_REQUIRED`.
- O workflow `Golden Test Advanced` conclui com sucesso no GitHub Actions para o SHA final.
