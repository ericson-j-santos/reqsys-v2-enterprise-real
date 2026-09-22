# Tasks — backlog-redmine-sync

## Implementadas (evidencia: commit `0290d6cb`, merge `15d6e976` / PR #1211)

- [x] **1.1** Adapter Dataverse OData generico (`dataverse_queue_client.py`) — token
      client-credentials, resolucao de EntitySetName ao vivo, `list_rows`/`update_row`/
      `create_row`
- [x] **1.2** Diagnostico de coluna (`metadados_coluna`) para o bug de truncamento de
      CorrelationId
- [x] **2.1** Orquestracao `redmine_sync_queue.py`: `limpar_reservas_travadas` (timeout
      15min) + `processar_fila_redmine`
- [x] **2.2** Escrita de volta SENT/ERROR em RedmineQueue + AgileSync + `cr85a_auditlog`
- [x] **3.1** API `redmine_sync.py`: `POST /processar` (admin/service-token, `dry_run`),
      `GET /status`, `GET /diagnostico/coluna`
- [x] **3.2** Settings novos em `config.py` + `.env.example`
      (`REDMINE_SYNC_DATAVERSE_URL/LOTE_MAX/RESERVA_TIMEOUT_MINUTOS/MAX_TENTATIVAS`)
- [x] **4.1** Docs de arquitetura (`docs/architecture/redmine-sync-queue.md`)
- [x] **4.2** 14 testes unitarios (mocks) para o worker/API
- [x] **4.3** Script `scripts/configurar_redmine_sync_queue.py`
      (`status`/`capturar`/`verificar`/`tudo`) — 11 testes adicionais para `dataverse_queue_client.py`

## Pendentes — configuracao e validacao ao vivo

- [ ] **5.1** Preencher `REDMINE_API_KEY`, `REDMINE_PROJECT_ID`, `REDMINE_SYNC_DATAVERSE_URL`
      no `.env` real (ainda vazios — verificado em 2026-08-16). Proximo passo literal:
      `python scripts/configurar_redmine_sync_queue.py capturar`
- [ ] **5.2** Rodar `python scripts/configurar_redmine_sync_queue.py verificar` para
      confirmar Application User no Dataverse + schema real das 3 tabelas `cr85a_*`
      (inclui o check de MaxLength do CorrelationId)
- [ ] **5.3** Confirmar existencia de `cr85a_reservedat`, `cr85a_retrycount`,
      `cr85a_errordetail` em `cr85a_redminequeue` (via `GET /diagnostico/coluna` ou
      `verificar`) — hoje assumidas por convencao, nao confirmadas
- [ ] **5.4** Primeiro teste real de ponta a ponta com `dry_run=true`, depois
      `--criar-issue-teste` (cria issue real no Redmine — opt-in deliberado, avisar o
      usuario antes de rodar)
- [ ] **5.5** Decidir se/quando automatizar a chamada a `/processar` (cron/GitHub
      Actions/Power Automate Recurrence com `X-Service-Token`) — deliberadamente nao
      implementado ainda (ver design.md)
