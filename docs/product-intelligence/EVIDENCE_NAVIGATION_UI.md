# Product Intelligence Evidence Navigation UI

## Objetivo

Adicionar uma camada navegável e executiva para o `Product Intelligence Final Evidence Index`, sem alterar decisões de produção e sem substituir revisão humana.

## Estratégia de implementação

- Branch limpa criada a partir da `main` atual.
- Incremento isolado em modo `review_only`.
- Sem alteração em runtime produtivo.
- Sem mudança em secrets, deploy ou gates de produção.
- Saídas versionáveis em JSON, Markdown e HTML.

## Artefatos gerados

| Artefato | Finalidade |
|---|---|
| `product-intelligence-evidence-navigation-ui.json` | Índice estruturado para futura UI dinâmica |
| `product-intelligence-evidence-navigation-ui.md` | Sumário operacional para GitHub Actions |
| `product-intelligence-evidence-navigation-ui.html` | Navegação executiva autocontida |

## Regras de status

| Condição | Status |
|---|---|
| Cobertura 100% e risco até 5% | Verde / consolidado |
| Cobertura >= 80% e risco até 20% | Amarelo / requer revisão |
| Abaixo dos critérios anteriores | Vermelho / bloqueado |

## Guardrail

Este incremento não autoriza decisões automáticas de produção. O resultado permanece `review_only` e requer revisão humana de governança antes de uso operacional vinculante.
