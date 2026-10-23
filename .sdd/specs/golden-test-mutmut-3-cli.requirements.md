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
10. Os testes de qualidade de IA devem usar o `db_session` isolado em memória, sem compartilhar o banco global carregado por outros módulos da suíte.
11. Tokens escopados gravados diretamente pelo teste do cofre devem ter valor exclusivo por execução para não colidir com o hash único persistido por fases anteriores.
12. Cada cenário de memória Planner/Copilot deve gerar um `planner_task_id` novo no momento da execução, inclusive quando o Mutmut repete a suíte no mesmo processo.
13. Mocks que retornam coleções mutáveis no sync Figma/GitHub devem criar uma coleção nova dentro de cada execução do teste.
14. Cenários parametrizados de monitoramento GovBI devem construir uma resposta HTTP nova por execução, sem reutilizar streams consumidos ou fechados.
15. O ajuste não deve executar deploy, alterar ambientes, acessar segredos ou realizar merge.

## Critérios de aceite

- `tests/test_golden_test_advanced_contract.py` passa integralmente.
- `backend/tests/test_agile_package_registry.py` passa em execuções consecutivas contra o banco de teste persistente.
- `backend/tests/test_ai_quality_critical_paths.py` passa independentemente dos dados gravados por outros testes.
- O cenário `test_token_escopado_precisa_autorizar_chave_alvo` passa em execuções consecutivas sem reutilizar `token_hash`.
- `backend/tests/test_copilot_memory_service.py` passa quando executado duas vezes no mesmo processo sem reutilizar `planner_task_id`.
- `backend/tests/test_figma_github_sync_critical_paths.py` passa quando executado duas vezes no mesmo processo sem reaproveitar comentários adicionados ao mock.
- `backend/tests/test_monitoramento_snapshot_critical_paths.py` passa quando executado duas vezes no mesmo processo sem reaproveitar respostas HTTP consumidas.
- O carregador de configuração do Mutmut 3.8.0 reconhece `source_paths`, `only_mutate` e `pytest_add_cli_args_test_selection`.
- O Pre-PR Readiness admite o SHA final sem bloqueio `SDD_SPEC_REQUIRED`.
- O workflow `Golden Test Advanced` conclui com sucesso no GitHub Actions para o SHA final.

