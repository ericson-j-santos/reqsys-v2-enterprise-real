# Product Intelligence Evidence Navigation Compliance Drift Index

## Objetivo

Criar um índice de drift de compliance para os artifacts review-only da Evidence Navigation, bloqueando avanço governado quando houver desvio de modo, revisão humana, hash, ciclo de vida ou autorização produtiva.

## Escopo

- Geração de índice JSON de compliance drift.
- Geração de sumário Markdown.
- Validação da cadeia anterior: lifecycle index.
- Upload de bundle de drift pelo GitHub Actions.

## Drifts monitorados

| Código | Severidade | Regra |
|---|---|---|
| `MODE_DRIFT` | Alta | O modo deve permanecer `review_only` |
| `PRODUCTION_PROMOTION_DRIFT` | Crítica | Promoção produtiva deve permanecer bloqueada |
| `HUMAN_REVIEW_DRIFT` | Alta | Revisão humana deve permanecer obrigatória |
| `LIFECYCLE_COMPLETENESS_DRIFT` | Alta | Lifecycle precisa estar completo |
| `ARTIFACT_HASH_DRIFT` | Média | Artifact precisa ter SHA-256 |
| `ARTIFACT_STATE_DRIFT` | Média | Artifact precisa estar pronto para review-only |

## Guardrails

- Não promove evidência para produção.
- Não altera secrets.
- Não altera deploy.
- Falha o workflow se drift de compliance for detectado.
