# Teams Commit Notification — gateway canônico

## Objetivo

Migrar a notificação automática de commits do webhook Power Automate direto para o Teams Messaging Gateway canônico do ReqSys, mantendo falha fechada quando a entrega não for confirmada.

## Requisitos

1. `.github/workflows/teams-commit-notification.yml` não deve consumir `TEAMS_WEBHOOK_URL` diretamente.
2. O workflow deve resolver `scripts/resolve_pc24x7_dev_locator.mjs`, validar assinatura/TTL/domínio e exportar o `selected_url` somente durante a execução como `TEAMS_GATEWAY_BASE_URL`.
3. O workflow não deve usar `vars.TEAMS_GATEWAY_BASE_URL`, `fly.io` ou `fly.dev`.
4. O envio deve usar `scripts/notificar_teams.py` com `TEAMS_GATEWAY_DESTINO_ID`.
5. O modo de entrega deve ser `flow_bot`.
6. A execução deve usar `--strict` para que falha de entrega permaneça visível no CI.
7. O contrato de CI deve impedir regressão para a rota de webhook direto.
8. Actions externas alteradas neste incremento devem usar SHA imutável.

## Critérios de aceite

- O contrato `Teams Commit Notification Contract` passa no HEAD exato do PR.
- O `Pre-PR Readiness Gate` aceita a especificação SDD e todos os invariantes preventivos do incremento.
- O workflow não contém variável de ambiente `TEAMS_WEBHOOK_URL`.
- O workflow contém o resolver assinado, `steps.locator.outputs.base_url`, `TEAMS_GATEWAY_DESTINO_ID`, `scripts/notificar_teams.py`, `flow_bot` e `--strict`.
- O workflow não contém `vars.TEAMS_GATEWAY_BASE_URL`, `fly.io` nem `fly.dev`.
- Após o merge, uma execução real de `Teams Commit Notification` confirma a entrega pelo gateway canônico antes de a correção funcional ser declarada concluída.

## Rollback

Reverter os commits do PR. Nenhum segredo é criado, removido ou alterado por esta mudança.
