# Fly.io — retirada definitiva de todos os ambientes

## Decisão

Em 2026-10-02 o usuário determinou retirar Fly.io definitivamente de todas as soluções. Esta decisão substitui a autorização histórica de HML/PROD manual em `pc24x7-dev-fly-retirement.requirements.md`.

## Requisitos deste hotfix

1. Bloquear jobs com operações, credenciais ou callers Fly.io em DEV/HML/STG/PROD com condição constante falsa.
2. Preservar condições anteriores de autorização sob `false && (...)` e interfaces dos workflows reutilizáveis.
3. Validar YAML e regressão; detectar reativação e expressões que não bloqueiam realmente, como `false || true`.
4. Não apagar apps, bancos ou volumes e não revogar credenciais antes de migração/backup validados.
5. Jobs skipped não comprovam disponibilidade, deploy, migração ou encerramento remoto.
6. Revisão de chamadas indiretas, GitLab, scripts, configs, consumidores e encerramento de cobrança permanece obrigatória para concluir a retirada integral.

## Critérios de aceite

- Todos os jobs Fly.io identificados estão bloqueados; casos negativos detectam reativação.
- YAML e testes regressivos passam no SHA da mudança.
- Builds independentes do Fly.io e contratos de autorização são preservados.
- CI de admissão e revisão de evidência passam antes do merge.
