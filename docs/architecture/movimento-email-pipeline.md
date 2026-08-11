# Migração da rotina de e-mail — Prospecção Movimento / Portabilidade Consignado (#2861)

## Decisão

A rotina diária de e-mail do relatório SSRS legado de Prospecção Movimento —
Portabilidade Consignado é substituída por um pipeline Python nativo do
ReqSys: extração dos 4 datasets do SQL Server corporativo, transformação,
renderização HTML/texto (Jinja2), enfileiramento durável e envio via SMTP —
exposto em `/v1/movimento-email`.

```text
SQL Server (origem)              ReqSys — app/services/movimento_email/
     |                                          |
     |  repository.py (pyodbc, retry+circuito)  |
     v                                          v
[4 datasets] -----------------> transform.py --> ContextoEmailMovimento
                                                  |
                                                  v
                                       email_service.py (Jinja2)
                                                  |
                                                  v
                                    queue_repository.py (fila durável)
                                                  |
                                    consumer.py (limpa reservas travadas
                                                  -> reserva lote -> SMTP)
                                                  |
                                                  v
                                          smtp_sender.py -> SMTP
```

Casos de uso (`jobs.py`, `consumer.py`) dependem de portas
(`ProspeccaoMovimentoRepository`, `EmailSender`) — nunca de pyodbc/smtplib
diretamente (ADR-001). O domínio (`models.py`, `transform.py`) é composto só
por dataclasses e funções puras.

### Por que a fila é SQLAlchemy e não MongoDB

A documentação original do time (`LT MENSAGERIA PROSPECCAO PYTHON.docx`)
descreve uma fila MongoDB (`Aplicação -> MongoDB -> Fila -> Consumer ->
SMTP`). Este projeto não tem MongoDB provisionado nem credenciais nesta
sessão; a base já provisionada do ReqSys (SQLAlchemy, tabela
`movimento_email_dispatch`) resolve o mesmo papel — fila durável com estado
`PENDING/PROCESSING/SENT/ERROR` — sem introduzir uma dependência de infra não
testável agora. `queue_repository.py` é a porta; um adapter MongoDB pode
substituí-la depois sem alterar `consumer.py`/`jobs.py`.

## Estado atual x alvo x gaps (ADR-012)

| Item | Estado |
|---|---|
| Domínio (`models.py`, `transform.py`) | ✅ Implementado e testado (dataclasses puras) |
| Template HTML + fallback texto (`email_movimento.html`, `email_service.py`) | ✅ Implementado e testado (autoescape Jinja2 ligado) |
| Fila durável com limpeza de reservas travadas (`queue_repository.py`) | ✅ Implementado e testado (timeout 15min configurável, ver CLAUDE.md do usuário) |
| Consumer (`consumer.py`) com `dry_run` estruturalmente distinto de envio real | ✅ Implementado e testado |
| Job diário (`jobs.py`): extração -> transformação -> renderização -> fila | ✅ Implementado e testado (com repositório dublê) |
| `POST /v1/movimento-email/jobs/executar`, `POST /v1/movimento-email/fila/consumir`, `GET /v1/movimento-email/status` | ✅ Implementado e testado |
| Adapter real de extração (`SqlServerProspeccaoMovimentoRepository`, pyodbc + retry + circuit breaker) | ✅ Implementado — **não testado contra o SQL Server real** |
| DDL das 4 views de origem — versionada, idempotente, autocontida (`sql/views/V1__*.sql` + `MANIFEST.json` + `scripts/aplicar_movimento_email_views.py`) | ✅ Implementado — `CREATE OR ALTER VIEW`, checksum SHA-256 contra o manifesto, `--dry-run`, transação com rollback automático em falha, rollback explícito (`--confirmar`) |
| Nomes reais das views/tabelas de origem (fechamento diário, pendências de cadastro/históricas/observação) | ⛔ **Gap #1 (restante)** — a DDL em si está pronta e é deployável hoje (`V1` cria as 4 views com o contrato de colunas certo), mas o corpo é um stub `WHERE 1 = 0`: falta a equipe de dados confirmar o `FROM`/`JOIN` real contra o schema do SSRS legado e descomentar o exemplo já deixado em cada arquivo — ver `sql/views/README.md` |
| Adapter real de envio (`SmtpEmailSender`) | ✅ Implementado — **não testado contra um servidor SMTP real** (sem `MOVIMENTO_EMAIL_SMTP_*` configurado nesta sessão) |
| Agendamento diário automático (scheduler/cron) | ⏳ Fora de escopo desta entrega — hoje disparado sob demanda via API (mesma decisão do Redmine Sync Queue: evitar poll contínuo sem visibilidade operacional) |
| Config centralizada em YAML (como descrito na doc original) | ⏳ Decisão: usar o padrão já existente do projeto (`pydantic-settings` + `.env`, ver `MOVIMENTO_EMAIL_*` em `.env.example`) em vez de introduzir um segundo mecanismo de configuração |
| Retenção/expurgo de itens `SENT` antigos em `movimento_email_dispatch` | ⏳ Não implementado nesta entrega |

## Configuração (`MOVIMENTO_EMAIL_*`, ver `.env.example`)

| Variável | Uso |
|---|---|
| `MOVIMENTO_EMAIL_SOURCE_DSN` | Connection string pyodbc completa do SQL Server de origem |
| `MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS` | Timeout por consulta de extração (padrão 30s) |
| `MOVIMENTO_EMAIL_SMTP_HOST/PORT/USER/PASSWORD/USE_TLS/FROM` | Credenciais SMTP (nunca hardcoded — ADR-002) |
| `MOVIMENTO_EMAIL_RECIPIENTS` | Lista de destinatários padrão, separados por vírgula (pode ser sobrescrita por request) |
| `MOVIMENTO_EMAIL_LOTE_MAX` / `_RESERVA_TIMEOUT_MINUTOS` / `_MAX_TENTATIVAS` | Mesma semântica do Redmine Sync Queue |

## Próximos passos para ir a produção

1. Confirmar com a equipe de dados os nomes reais das 4 views/tabelas de
   origem e atualizar `app/services/movimento_email/sql/*.sql` (gap #1).
2. Configurar `MOVIMENTO_EMAIL_SOURCE_DSN` e validar `POST
   /v1/movimento-email/jobs/executar` contra a origem real.
3. Configurar `MOVIMENTO_EMAIL_SMTP_*` e validar `POST
   /v1/movimento-email/fila/consumir` (começar com `dry_run=true`).
4. Decidir e implementar o agendamento diário (cron externo chamando
   `jobs/executar` + `fila/consumir`, ou scheduler interno).
