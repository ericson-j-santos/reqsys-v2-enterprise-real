# Product Intelligence Evidence Navigation Governance Lifecycle Index

## Objetivo

Criar um índice de ciclo de vida governado para os artifacts review-only da Evidence Navigation, conectando geração, publicação para revisão, retenção, revisão humana e promoção/regeneração controlada.

## Escopo

- Geração de índice JSON de lifecycle.
- Geração de sumário Markdown.
- Validação da cadeia anterior: publisher + retention index.
- Upload de bundle de lifecycle pelo GitHub Actions.

## Ciclo governado

```text
generated → published_for_review → retained_review_only → reviewed_by_human_governance → promoted_or_regenerated
```

## Guardrails

- O índice é `review_only`.
- Não promove evidência para produção.
- Não altera secrets.
- Não altera deploy.
- Não executa decisão produtiva automática.
- Promoção produtiva exige aprovação humana de governança.

## Critério de sucesso

O workflow só fica verde quando todos os artifacts possuem retenção, SHA-256, estado de lifecycle completo, revisão humana obrigatória e promoção produtiva bloqueada por padrão.
