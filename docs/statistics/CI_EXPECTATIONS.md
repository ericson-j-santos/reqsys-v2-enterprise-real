# Expectativas de CI — Aba Estatísticas v1

## Checks esperados

- Instalação de dependências do frontend.
- Lint/format quando configurado.
- Testes unitários, incluindo `estatisticas.test.js`.
- Build do frontend.
- Testes E2E/smoke existentes.

## Sinais de falha prováveis

| Falha | Correção esperada |
|---|---|
| Import de Vuetify não resolvido | Confirmar que componentes usados existem na versão atual |
| Test runner não encontra arquivo | Ajustar padrão de descoberta de testes |
| Build falha por rota | Confirmar import `EstatisticasView` e caminho relativo |
| Snapshot/smoke falha por menu | Atualizar expectativa de navegação |

## Pós-CI

- Se CI falhar, corrigir antes de qualquer expansão.
- Se CI ficar verde, revisar conflito com PRs paralelos que alteram router/layout.
