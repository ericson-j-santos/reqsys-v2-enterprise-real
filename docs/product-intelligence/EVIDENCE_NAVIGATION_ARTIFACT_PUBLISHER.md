# Product Intelligence Evidence Navigation Artifact Publisher

## Objetivo

Publicar, em modo `review_only`, um bundle rastreável dos artefatos da Evidence Navigation UI para facilitar auditoria, revisão humana e navegação operacional.

## Escopo

- Geração de manifesto JSON com SHA-256, tamanho e disponibilidade de cada artefato.
- Geração de resumo Markdown para GitHub Step Summary.
- Upload de artifact `product-intelligence-evidence-navigation-review-bundle` pelo GitHub Actions.
- Retenção inicial: 14 dias.

## Artefatos incluídos no bundle

| Artefato | Finalidade |
|---|---|
| `product-intelligence-evidence-navigation-ui.json` | Estrutura indexada para UI dinâmica |
| `product-intelligence-evidence-navigation-ui.md` | Sumário operacional |
| `product-intelligence-evidence-navigation-ui.html` | Visual navegável autocontido |
| `product-intelligence-evidence-navigation-artifact-manifest.json` | Manifesto auditável |
| `product-intelligence-evidence-navigation-artifact-manifest.md` | Resumo executivo do publisher |

## Guardrails

- Não publica em produção.
- Não usa secrets.
- Não altera deploy.
- Não autoriza decisão produtiva automática.
- Exige revisão humana de governança para uso vinculante.

## Critério de sucesso

O workflow só fica verde quando todos os artifacts obrigatórios existem, têm conteúdo, possuem hash SHA-256 e o estado final é `EVIDENCE_NAVIGATION_ARTIFACTS_PUBLISHABLE`.
