# Authorized Actions Gateway — concorrência por comentário

## Contexto

O GitHub Actions mantém no máximo um run pendente por grupo de concorrência. Um grupo compartilhado por issue permite que um novo comentário substitua outro comentário autorizado ainda pendente, mesmo com `cancel-in-progress: false`.

## Requisitos

1. Cada evento `issue_comment.created` deve usar o `github.event.comment.id` imutável como parte do grupo de concorrência.
2. O grupo não pode depender do texto do comentário nem de outro campo controlado pelo usuário.
3. `cancel-in-progress` deve permanecer `false`.
4. A allowlist de issue, autor, comandos e workflows-alvo não deve ser ampliada.
5. Workflows-alvo continuam responsáveis por sua própria concorrência e idempotência.
6. Teste regressivo deve rejeitar o agrupamento apenas por issue e qualquer uso do corpo do comentário no bloco de concorrência.
7. A mudança não executa deploy, produção, segredo ou alteração de permissão.

## Critérios de aceite

- workflow YAML válido;
- teste focal aprovado;
- gate SDD aprovado;
- `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`;
- E2E posterior comprova que dois comentários allowlisted distintos não se cancelam antes do dispatch.
