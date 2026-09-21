# Pre-PR Static Quality Enforcement

## Objetivo

Eliminar a classe recorrente de falhas determinísticas descobertas somente após a abertura da PR, antecipando lint, sintaxe shell e testes contratuais relacionados ao diff para o `Pre-PR Readiness Gate`.

## Classificação

`gap_fix`.

## Problema evidenciado

O gate pré-PR compilava Python, mas não executava Ruff nos arquivos alterados. Assim, erros estáticos como imports não utilizados podiam atravessar `READY_FOR_PR` e falhar apenas no CI da PR. Além disso, testes agregados que referenciavam um script/workflow alterado sem seguir o padrão `test_<script>.py` podiam não ser selecionados.

## Requisitos

1. Todo arquivo Python alterado deve passar `py_compile` e `ruff check` antes de `READY_FOR_PR=passed`.
2. Todo shell `.sh` alterado deve passar `bash -n`.
3. O seletor de testes deve incluir testes alterados, testes pelo nome convencional, testes Python declarados no SDD alterado e testes contratuais que referenciem arquivos alterados por referências específicas; nomes de arquivo ou stems genéricos como `main.js`, `index.html`, `main` e `index` não podem selecionar suites sem relação.
4. O workflow Pre-PR deve instalar Ruff antes da validação.
5. `Pre-PR Readiness Gate` deve ser obrigatório em `governance/merge/current-sha-required-workflows.json` e executar tanto em `push` quanto em `pull_request` para o SHA exato da branch do PR.
6. O workflow não pode ser tratado como opcional quando ausente/falho.
7. Evidência continua vinculada ao `head_sha` exato e `behind_by=0`.
8. Nenhum merge, deploy ou produção é realizado por este incremento.
9. Uma PR sem alterações de backend não pode executar pytest de backend por mera coincidência textual com nomes genéricos de arquivos.

## Controles negativos

- Ruff vermelho => `READY_FOR_PR=blocked`;
- `bash -n` vermelho => `READY_FOR_PR=blocked`;
- teste contratual relacionado vermelho => `READY_FOR_PR=blocked`;
- ausência/falha do `Pre-PR Readiness Gate` no evento `pull_request` e SHA atual => Governed Merge Queue não libera merge;
- evidência de SHA anterior não é válida.

## Critérios de aceite

- testes de `tests/test_pre_pr_readiness.py` verdes;
- `Guard Rail — Prontidão para PR` verde;
- `Pre-PR Readiness Gate` verde no HEAD final;
- política de merge exige `Pre-PR Readiness Gate`;
- CI completo da PR verde no mesmo HEAD.
