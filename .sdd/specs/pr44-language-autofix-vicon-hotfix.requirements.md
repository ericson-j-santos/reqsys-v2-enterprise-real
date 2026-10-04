# Hotfix do autofix de linguagem após o PR #44

## Objetivo

Corrigir a regressão pós-merge em que o autofix de linguagem traduziu parte de um identificador técnico de `<v-icon>`, além de impedir que o mesmo tipo de alteração volte a ocorrer.

## Requisitos

1. A Arquitetura Viva deve usar um identificador de ícone válido e não traduzido.
2. O autofix de linguagem deve preservar o conteúdo técnico de `<v-icon>`.
3. O validador de linguagem deve ignorar o identificador técnico dentro de `<v-icon>`.
4. O texto humano adjacente ao ícone deve continuar sujeito à validação e à autocorreção de linguagem simples.
5. A correção deve permanecer restrita ao frontend e não executar deploy, alteração de dados, segredos ou promoção de ambiente.

## Critérios de aceite

- `frontend/scripts/fix-user-facing-language.test.mjs` comprova que `mdi-source-branch` permanece intacto enquanto “Abrir branch” é simplificado.
- `frontend/scripts/validate-user-facing-language.test.mjs` comprova que o identificador de ícone é ignorado e o texto humano adjacente continua sendo detectado.
- `frontend/src/views/ArquiteturaVivaView.vue` não contém `mdi-source-versão de código`.
- O HEAD atual passa pelo contrato SDD, Pre-PR Readiness e demais gates obrigatórios antes do merge.
- Após o merge, uma leitura independente da `main` confirma o ícone corrigido e as proteções preventivas.
