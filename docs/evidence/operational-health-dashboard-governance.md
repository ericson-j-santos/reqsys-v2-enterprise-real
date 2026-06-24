# Evidence — Operational Health Dashboard Governance

## Incremento

Operational Health Dashboard Governance.

## Objetivo

Registrar evidência versionada para as próximas prioridades reais após estabilização acelerada da `main`.

## Capacidades cobertas

- PR aging.
- Conflict risk.
- Stale branch index.
- CI health trend.
- Merge readiness score.
- Classificação operacional de PRs.

## Estado alvo

| Capacidade | Estado alvo |
|---|---|
| PR aging | Governado |
| Conflict risk | Governado |
| Stale branch index | Governado |
| CI health trend | Evidenciado |
| Merge readiness score | Documentado |
| Classificação operacional | Documentada |

## Critérios de aceite

- Documento operacional versionado.
- Workflow de evidência review-only versionado.
- Gatilho manual disponível.
- Gatilho em PR disponível.
- Gatilho em push/main disponível.
- Sem alteração produtiva.

## Guardrails

- Não executa deploy.
- Não altera produção.
- Não altera permissões.
- Não altera segredos.
- Não executa merge automático.
- Não fecha PRs automaticamente.

## Próximo incremento recomendado

Transformar a evidência estática em gerador automático de artifacts JSON/Markdown/HTML com dados reais dos PRs abertos e runs recentes.
