# Dicionário de dados — Autonomous Delivery Cycle

| Campo | Descrição |
|---|---|
| `schema_version` | Versão do contrato JSON |
| `generated_at` | Data/hora da geração |
| `repo` | Repositório avaliado |
| `mode` | `dry_run`, `merge_enabled` ou `seed` |
| `required_label` | Label exigida para autorização |
| `candidate_count` | Quantidade de PRs candidatos |
| `eligible_count` | Quantidade de PRs elegíveis |
| `merged_count` | Quantidade de PRs mergeados |
| `decisions` | Decisões por PR |
| `blockers` | Motivos que impedem merge |
| `post_merge` | Resultado observado após merge |
| `next_increments` | Incrementos capturados do corpo do PR |
