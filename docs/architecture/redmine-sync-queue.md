# Redmine Sync Queue — Worker Python para o fluxo PA-001-CreateRedmineIssue

## Decisão

O fluxo Power Automate `PA-001-CreateRedmineIssue` (Planner → Dataverse) não pode
chamar o Redmine diretamente porque o conector HTTP genérico está bloqueado por
DLP no tenant. A persistência em Dataverse (`cr85a_redminequeue`,
`cr85a_agilesync`, `cr85a_auditlog`) já resolve o lado Power Automate. O ReqSys
passa a expor o lado que faltava: um worker que lê `cr85a_redminequeue`, cria a
issue real no Redmine e devolve o resultado para Dataverse — em
`/v1/redmine-sync`.

```text
[Power Automate: PA-001]                    [ReqSys: /v1/redmine-sync]
When a task created                                    |
  -> Compose_CorrelationId                              |
  -> AuditLog (cr85a_auditlog)                          |
  -> Get Task Details                                   |
  -> Compose_TrackerCode / TrackerMapping / TrackerId    |
  -> RedmineQueue (Status=PENDING)   ---leitura--->  processar_fila_redmine()
  -> AgileSync (Status=NEW)                              |  cria issue no Redmine
                                                          |  (github_redmine.criar_issue_generica)
                                        <---escreve---    v
                                     RedmineQueue.Status = SENT|ERROR
                                     AgileSync.cr85a_plannerstatus = SYNCED|ERROR
                                     AuditLog: REDMINE_ISSUE_CREATED|FAILED
```

## Estado atual x alvo x gaps (ADR-012)

| Item | Estado |
|---|---|
| `POST /v1/redmine-sync/processar` (lote real + `dry_run`) | ✅ Implementado nesta entrega |
| `GET /v1/redmine-sync/status` (contagem por status) | ✅ Implementado |
| `GET /v1/redmine-sync/diagnostico/coluna` (Data Type + MaxLength ao vivo) | ✅ Implementado |
| Limpeza de reservas travadas (`PROCESSING` > timeout) | ✅ Implementado (`limpar_reservas_travadas`, ver CLAUDE.md do usuário) |
| Mascaramento de segredo em `ErrorDetail` (ADR-002) | ✅ Implementado |
| Chamada real ao Redmine + validação em ambiente real | ⏳ **Não testado ao vivo** — nenhuma credencial `REDMINE_*`/`REDMINE_SYNC_DATAVERSE_URL` configurada nesta sessão |
| Colunas novas necessárias em `cr85a_redminequeue` (ver abaixo) | ⛔ **Ainda não existem** no Dataverse — bloqueador para rodar de ponta a ponta |
| `cr85a_correlationid` truncando em `cr85a_agilesync` | ⛔ Bloqueador original do usuário — agora diagnosticável em 1 chamada, ver seção própria |
| Agendamento automático (poll contínuo) | ⏳ Deliberadamente **não implementado** — ver "Por que só sob demanda" |
| Hierarquia Épico/HU, Status Sync bidirecional (Redmine → Planner) | ⏳ Fora de escopo desta entrega |

## Pré-requisito: colunas que faltam no Dataverse

`cr85a_redminequeue` hoje (confirmado pelo usuário) tem: `CorrelationId`,
`PlannerTaskId`, `TrackerCode`, `TrackerId`, `Subject`, `Status`. Para o worker
fechar o loop, crie estas colunas adicionais na tabela (Maker Portal →
`cr85a_redminequeue` → Colunas):

| Coluna (lógica assumida) | Tipo | Tamanho/obs. |
|---|---|---|
| `cr85a_reservedat` | Data e Hora | usada para liberar reservas travadas após timeout |
| `cr85a_retrycount` | Número Inteiro | contador de tentativas (ADR-010: proíbe retry infinito) |
| `cr85a_errordetail` | Texto (multilinha) | mensagem de erro mascarada (sem segredo) |
| `cr85a_redmineissueid` | Número Inteiro | **opcional** — se ausente, o worker apenas loga e segue (não falha o item) |

Se qualquer nome lógico divergir do assumido (`cr85a_<campo em minúsculas>`,
mesma convenção já confirmada em `cr85a_agilesync`), use
`GET /v1/redmine-sync/diagnostico/coluna?tabela=cr85a_redminequeue&coluna=<nome>`
para confirmar antes de configurar em produção.

## Resolvendo o bloqueador atual: `cr85a_correlationid` truncando em `cr85a_agilesync`

Em vez do passo manual (abrir Dataverse → Tabela → Coluna e ler Data Type/Maximum
Length na tela), chame:

```http
GET /v1/redmine-sync/diagnostico/coluna?tabela=cr85a_agilesync&coluna=cr85a_correlationid
```

A resposta traz `attribute_type` e `max_length` reais (via Dataverse Metadata API,
`EntityDefinitions(...)/Attributes(...)/Microsoft.Dynamics.CRM.StringAttributeMetadata`)
e, se `max_length < 36`, um `alerta` explícito confirmando a Hipótese 1 (coluna
curta demais para um `guid()`, que sempre tem 36 caracteres) e recomendando
aumentar para pelo menos 36 (100 recomendado).

Se em vez disso `attribute_type` vier diferente de `String`/`Memo` — por
exemplo `Lookup` — é a Hipótese 2 confirmada (o campo não é um texto simples;
o Power Automate está tentando gravar um objeto onde um texto era esperado).
Nesse caso o fluxo precisa mapear o campo para o `Outputs` puro de
`Compose_CorrelationId` (a string, não o objeto do compose), não a referência
ao card do compose inteiro.

O worker (`redmine_sync_queue.py`) sempre grava `cr85a_correlationid` como
string simples (`item.get('cr85a_correlationid')`), nunca como objeto — não
reproduz a Hipótese 2 nas próprias escritas.

## Confiabilidade (ADR-010 / ADR-011)

- **Reserva de registros + limpeza de estado travado**: cada lote primeiro chama
  `limpar_reservas_travadas` (timeout padrão 15 min, `REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS`),
  devolvendo para `PENDING` qualquer item preso em `PROCESSING` (ex.: o worker
  caiu no meio do processamento) antes de reservar um novo lote. Cada limpeza
  gera um evento de auditoria `QUEUE_RESERVATION_TIMEOUT_RECOVERED`.
- **Limite de tentativas**: após `REDMINE_SYNC_MAX_TENTATIVAS` (padrão 5) falhas
  consecutivas, o item vai para `ERROR` definitivo em vez de voltar para
  `PENDING` indefinidamente — nunca há retry infinito.
- **`dry_run`**: `POST /processar {"dry_run": true}` lista o que seria
  processado sem chamar o Redmine nem gravar nada; a resposta tem formato
  próprio (`seriam_processados`, `enviado: false`) — nunca é indistinguível de
  um processamento real.
- **Mascaramento**: qualquer `ErrorDetail` persistido no Dataverse passa por
  `_mascarar()`, removendo `X-Redmine-API-Key`/`Bearer <token>` antes de
  gravar (ADR-002).
- **Auditoria dupla**: cada evento é gravado tanto em `cr85a_auditlog`
  (Dataverse, mesma trilha que o flow já usa, correlacionável de ponta a
  ponta) quanto localmente via `registrar_evento` (auditoria própria do
  ReqSys) — a falha de uma não bloqueia a outra.

## Por que só sob demanda (sem poll automático contínuo)

`POST /v1/redmine-sync/processar` exige `JWT admin` ou `X-Service-Token` com
escopo `redmine_sync:processar` — não há um loop em background chamando isso
sozinho. Criar issues reais no Redmine é uma ação com efeito colateral externo
real (ADR-011: ações autônomas em produção exigem autorização/política
explícita); a entrega atual prioriza um endpoint auditável, chamável por um
agendador externo (cron, GitHub Actions, ou o próprio Power Automate via um
step "Recurrence" apontando para este endpoint) sobre rodar irrestrito dentro
do processo da API. Se o volume justificar automação futura, o próximo passo
natural é gerar um `X-Service-Token` escopado (`POST /v1/service-tokens`) e
agendar a chamada externamente — não adicionar um loop always-on sem essa
decisão explícita do usuário.

## Endpoints

| Rota | Autenticação | Uso |
|---|---|---|
| `GET /v1/redmine-sync/status` | JWT admin | Contagem por status (`PENDING`/`PROCESSING`/`SENT`/`ERROR`) + saúde (verde/azul/vermelho) |
| `POST /v1/redmine-sync/processar` | JWT admin OU `X-Service-Token` escopo `redmine_sync:processar` | Processa um lote (ou `dry_run`) |
| `GET /v1/redmine-sync/diagnostico/coluna` | JWT admin | Data Type + MaxLength ao vivo de qualquer coluna Dataverse |

## Configuração (`.env`)

```bash
AZURE_TENANT_ID=...          # já usado por hub_lowcode/teams_gateway
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
REDMINE_BASE_URL=...
REDMINE_API_KEY=...
REDMINE_PROJECT_ID=...
REDMINE_SYNC_DATAVERSE_URL=https://orga258f260.crm2.dynamics.com   # ambiente onde vivem as tabelas cr85a_*
REDMINE_SYNC_LOTE_MAX=20
REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS=15
REDMINE_SYNC_MAX_TENTATIVAS=5
```

`AZURE_CLIENT_ID` precisa ter um Dataverse Application User no ambiente de
`REDMINE_SYNC_DATAVERSE_URL` (mesmo procedimento já documentado em
`docs/architecture/teams-messaging-gateway.md`: `pac admin application
register` + `pac admin assign-user --role "System Customizer"`).

## Script de captura + verificação: `scripts/configurar_redmine_sync_queue.py`

Fecha os gaps deixados na entrega original (nenhuma credencial real
configurada, schema assumido por convenção, nada testado ao vivo) num único
lugar, no mesmo espírito de `scripts/configurar-redmine.ps1`/`verificar-redmine.ps1`,
mas cobrindo também o lado Dataverse/Azure AD específico deste worker.

```bash
cd backend && .venv\Scripts\python.exe ..\scripts\configurar_redmine_sync_queue.py status
#   -> lista o que já está no .env, sem imprimir segredo em texto puro

.venv\Scripts\python.exe ..\scripts\configurar_redmine_sync_queue.py capturar
#   -> pergunta interativamente (getpass para segredos) cada variável que falta
#      e grava em .env; aceita também --redmine-base-url etc. para uso não interativo

.venv\Scripts\python.exe ..\scripts\configurar_redmine_sync_queue.py verificar
#   -> testa AO VIVO: aquisição de token Azure AD/Dataverse, Application User
#      do AZURE_CLIENT_ID no ambiente, schema real de cr85a_redminequeue/
#      cr85a_agilesync/cr85a_auditlog contra o que o código assume (inclui o
#      diagnóstico do bloqueador cr85a_correlationid), e conectividade de
#      leitura com o Redmine (login + projeto). --criar-issue-teste cria uma
#      issue real de teste (efeito colateral real, off por padrão).

.venv\Scripts\python.exe ..\scripts\configurar_redmine_sync_queue.py tudo
#   -> capturar + verificar em sequência
```

Exit code 0 = tudo verificado; 1 = ainda há gap (lista exatamente qual). Rodado
nesta sessão apenas em modo `status`/`verificar` contra o `.env` real do
usuário (sem gravar nada) — confirmou que `AZURE_TENANT_ID`/`AZURE_CLIENT_ID`/
`AZURE_CLIENT_SECRET` **já estão configurados** (reaproveitados do Teams
Gateway), mas `REDMINE_BASE_URL`/`REDMINE_API_KEY`/`REDMINE_PROJECT_ID`/
`REDMINE_SYNC_DATAVERSE_URL` ainda faltam — rodar `capturar` é o próximo passo
real para eliminar esse gap.
