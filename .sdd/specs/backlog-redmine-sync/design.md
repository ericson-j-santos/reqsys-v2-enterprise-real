# Design — backlog-redmine-sync

> Escrito em 2026-08-16 a partir do codigo implementado.

## Arquitetura

```
Power Automate PA-001-CreateRedmineIssue
        │ (Planner trigger, DLP bloqueia HTTP direto p/ Redmine)
        ▼
Dataverse: cr85a_redminequeue / cr85a_agilesync / cr85a_auditlog / cr85a_trackermapping
        │
        │  GET /v1/redmine-sync/processar  (admin JWT ou X-Service-Token)
        ▼
┌────────────────────────────────────────────────────────────┐
│ backend/app/api/redmine_sync.py                              │
│  POST /processar (dry_run opcional) · GET /status ·          │
│  GET /diagnostico/coluna                                     │
└───────────────────────┬────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│ backend/app/services/redmine_sync_queue.py                   │
│  1. limpar_reservas_travadas (timeout 15min, log)             │
│  2. processar_fila_redmine → le PENDING, reserva lote          │
│  3. github_redmine.criar_issue_generica() por item             │
│     (reusa retry + circuit-breaker existentes)                │
│  4. escreve SENT/ERROR de volta em RedmineQueue+AgileSync      │
│  5. _registrar_auditlog_dataverse (correlation_id)              │
└───────────────────────┬────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────┐
│ backend/app/services/dataverse_queue_client.py                │
│  adapter OData generico: _token, resolver_entity_set_name,     │
│  list_rows/update_row/create_row, metadados_coluna,             │
│  testar_autenticacao, verificar_application_user                │
└────────────────────────────────────────────────────────────┘
```

## Decisoes de design

1. **Sem loop de polling em background.** `/processar` e sempre on-demand (admin ou
   `X-Service-Token`). Motivo explicito: ADR-011 (Operacao Autonoma) exige cautela extra para
   escrita nao-atendida com efeito colateral externo real (criar issue de verdade no Redmine).
   Se o volume justificar automacao depois, o proximo passo documentado e um `X-Service-Token`
   + gatilho externo (cron/GitHub Actions/Power Automate Recurrence) — nao um loop silencioso
   dentro do processo.
2. **`dry_run` estruturalmente distinto de execucao real** — decisao explicita para nunca
   dar a falsa impressao de sucesso confirmado numa simulacao (memoria
   `feedback_never_fake_dry_run_success`).
3. **`EntitySetName` resolvido ao vivo via Metadata API**, nao hardcoded/adivinhado por
   pluralizacao — Dataverse nem sempre segue a regra simples de plural em ingles.
4. **Reuso deliberado**: token client-credentials reusa o padrao de `hub_lowcode.py`
   (`_token_dataverse`); chamada HTTP ao Redmine reusa retry/circuit-breaker existente em
   `github_redmine.py` em vez de reimplementar.

## Configuracao (settings novos em `config.py` + `.env.example`)

- `REDMINE_SYNC_DATAVERSE_URL` — ambiente Dataverse alvo
- `REDMINE_SYNC_LOTE_MAX` (default 20)
- `REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS` (default 15)
- `REDMINE_SYNC_MAX_TENTATIVAS` (default 5)
- `REDMINE_BASE_URL`, `REDMINE_API_KEY`, `REDMINE_PROJECT_ID`

## Riscos / o que falta para producao

- Colunas `cr85a_reservedat` (DateTime), `cr85a_retrycount` (Whole Number),
  `cr85a_errordetail` (Text) precisam existir em `cr85a_redminequeue` — nao confirmado no
  Dataverse real, so assumido por convencao de nomenclatura (`cr85a_<campo minusculo>`).
- Nomes logicos de coluna da tabela RedmineQueue foram assumidos (usuario so mostrou display
  names) — usar `GET /diagnostico/coluna` para confirmar antes de mexer no schema.
- Nenhuma validacao ao vivo contra Dataverse/Redmine reais foi feita ate 2026-08-16.
