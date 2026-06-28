# Segurança — Autonomous Delivery Cycle

## Segurança operacional

- Usa `GITHUB_TOKEN` com permissões mínimas para conteúdo, PRs, issues, actions, checks e statuses.
- Não acessa secrets externos.
- Não executa código vindo do corpo do PR.
- Não usa `pull_request_target`.
- Não faz checkout de branch de fork com permissão elevada.

## Segurança de merge

- Merge condicionado ao head SHA esperado.
- Merge condicionado a workflows obrigatórios verdes.
- Merge condicionado a labels explícitas.

## Segurança de continuidade

- Próximos incrementos são texto report-only.
- O chat/agente precisa validar contexto antes de executar qualquer item capturado.
