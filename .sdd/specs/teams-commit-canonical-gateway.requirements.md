# Teams Commit Notification — gateway canônico com contingência governada

## Objetivo

Manter o Teams Messaging Gateway PC24x7 como rota primária da notificação automática de commits e usar o webhook Power Automate governado apenas como contingência anterior ao envio quando o locator/runtime estiver indisponível. A execução permanece fail-closed quando nenhuma rota confirma a entrega.

## Requisitos

1. `.github/workflows/teams-commit-notification.yml` deve manter o locator assinado e o Teams Messaging Gateway como rota primária.
2. O workflow deve resolver `scripts/resolve_pc24x7_dev_locator.mjs`, validar assinatura/TTL/domínio e exportar o `selected_url` somente durante a execução como `TEAMS_GATEWAY_BASE_URL` quando o locator estiver vigente.
3. O workflow não deve usar `vars.TEAMS_GATEWAY_BASE_URL`, `fly.io` ou `fly.dev`.
4. O envio deve usar `scripts/notificar_teams.py` com `TEAMS_GATEWAY_DESTINO_ID`.
5. O modo de entrega deve ser `flow_bot`.
6. A execução deve usar `--strict` para que falha de entrega permaneça visível no CI.
7. Quando o locator não resolver antes de qualquer POST, o workflow pode usar `TEAMS_WEBHOOK_URL` + `TEAMS_WEBHOOK_RECIPIENT` pelo gerador autocontido, com Adaptive Card, correlation ID e event type específico de contingência.
8. O fallback não deve ser tentado após uma tentativa ambígua de envio pelo gateway, evitando entrega duplicada.
9. Se gateway e webhook não estiverem configurados ou não confirmarem entrega, o workflow deve permanecer vermelho, sem `continue-on-error`.
10. A evidência do run deve registrar a rota selecionada e sinalizar quando a contingência estiver ativa.
11. Actions externas alteradas neste incremento devem usar SHA imutável.
12. Ao baixar evidência de um workflow de origem, o cliente deve manter a autenticação somente no host da API GitHub e removê-la de redirecionamentos para outro host com URL assinada, evitando falha 401 e vazamento de credencial.
13. O supervisor local deve renovar o locator em intervalo de 6 minutos, manter o teto de 240 publicações agendadas por dia e usar um Python persistente dedicado com dependências fixadas.
14. Um monitor GitHub-hosted deve validar o locator a cada 10 minutos, exigir pelo menos 300 segundos de TTL restante e falhar fechado quando o contrato não estiver fresco.
15. O monitor deve alertar pelo webhook governado somente na primeira transição para falha e na recuperação subsequente, sem repetir alertas enquanto a falha persistir.
16. Cada execução do monitor deve publicar evidência sanitizada, sem segredo e sem tocar produção.

## Critérios de aceite

- O contrato `Teams Commit Notification Contract` passa no HEAD exato do PR.
- O `Pre-PR Readiness Gate` aceita a especificação SDD e todos os invariantes preventivos do incremento.
- O workflow contém o resolver assinado, `steps.locator.outputs.base_url`, `TEAMS_GATEWAY_DESTINO_ID`, `scripts/notificar_teams.py`, `flow_bot` e `--strict` como rota primária.
- O workflow contém fallback explícito com `TEAMS_WEBHOOK_URL`, `TEAMS_WEBHOOK_RECIPIENT`, `send-webhook`, Adaptive Card e `commit-notification-fallback`.
- O workflow não contém `vars.TEAMS_GATEWAY_BASE_URL`, `fly.io` nem `fly.dev`.
- O workflow não contém `continue-on-error`, falha quando as duas rotas estão indisponíveis e registra `delivery_route`.
- O download de artefatos de `workflow_run` remove `Authorization` em redirecionamentos entre hosts e preserva o token apenas para a API GitHub.
- O supervisor usa intervalo de 6 minutos, Python dedicado em `%LOCALAPPDATA%/ReqSys/RuntimeSupervisor/python` e continua abaixo do orçamento anônimo do ntfy.
- O job `watch-locator` do workflow `Teams Commit Notification` usa agenda de 10 minutos, TTL mínimo de 300 segundos, alerta de transição e artifact sanitizado.
- Após o merge, uma execução real de `Teams Commit Notification` com locator indisponível confirma a entrega pelo webhook governado e identifica a contingência no summary.

## Rollback

Reverter os commits do PR para retornar ao gateway-only. Nenhum segredo é criado, removido ou alterado por esta mudança.
