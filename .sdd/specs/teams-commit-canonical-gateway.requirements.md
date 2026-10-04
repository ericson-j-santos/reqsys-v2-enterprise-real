# Teams Commit Notification — gateway canônico

## Objetivo

Migrar a notificação automática de commits do webhook Power Automate direto para o Teams Messaging Gateway canônico do ReqSys, mantendo falha fechada quando a entrega não for confirmada.

## Requisitos

1. `.github/workflows/teams-commit-notification.yml` não deve consumir `TEAMS_WEBHOOK_URL` diretamente.
2. O envio deve usar `scripts/notificar_teams.py` com `TEAMS_GATEWAY_BASE_URL` e `TEAMS_GATEWAY_DESTINO_ID`.
3. O modo de entrega deve ser `flow_bot`.
4. A execução deve usar `--strict` para que falha de entrega permaneça visível no CI.
5. O contrato de CI deve impedir regressão para a rota de webhook direto.
6. Actions externas alteradas neste incremento devem usar SHA imutável.

## Critérios de aceite

- O contrato `Teams Commit Notification Contract` passa no HEAD exato do PR.
- O `Pre-PR Readiness Gate` aceita a especificação SDD e todos os invariantes preventivos do incremento.
- O workflow não contém variável de ambiente `TEAMS_WEBHOOK_URL`.
- O workflow contém `TEAMS_GATEWAY_BASE_URL`, `TEAMS_GATEWAY_DESTINO_ID`, `scripts/notificar_teams.py`, `flow_bot` e `--strict`.
- Após o merge, uma execução real de `Teams Commit Notification` confirma a entrega pelo gateway canônico antes de a correção funcional ser declarada concluída.

## Rollback

Reverter os commits do PR. Nenhum segredo é criado, removido ou alterado por esta mudança.
