# Release Note — PR CI Watch v1.0.0

## Resumo

Implementa watcher seguro para diagnóstico de CI em Pull Requests, com geração de evidência operacional e classificação de workflows por health.

## Entregas

- Workflow `.github/workflows/pr-ci-watch.yml`.
- Script `scripts/pr_ci_watch.py`.
- Runbook `docs/runbooks/pr-ci-watch.md`.
- Artifact `pr-ci-watch-report`.

## Benefício

Reduz validação manual de checks, cria rastreabilidade operacional e prepara a base para automação futura de ready-for-review e classificação de falhas.

## Segurança

- Não faz merge automático.
- Não altera produção.
- Não altera draft automaticamente.
- Usa `GITHUB_TOKEN` com permissões mínimas necessárias.

## Próximo incremento

Adicionar leitura de logs de jobs falhos e classificação automática da causa provável.
