# Requirements — backlog-redmine-sync

> Escrito em 2026-08-16 a partir do codigo ja implementado e mergeado (nunca existiu um
> requirements.md formal para este trabalho — reconstruido para dar rastreabilidade real).

## Contexto

O fluxo Power Automate `PA-001-CreateRedmineIssue` (Planner -> Dataverse) persiste itens em
`cr85a_redminequeue` porque o tenant tem uma politica de DLP que bloqueia chamada HTTP direta
do Power Automate para o Redmine. Sem um consumidor externo dessa fila, os itens ficam
parados em Dataverse e nunca viram issue real no Redmine.

## Requirement 1 — Processar fila pendente sob demanda

**User story:** Como operador, quero disparar o processamento da fila `cr85a_redminequeue`
sob demanda (admin ou token de servico), para criar os issues reais no Redmine sem depender
de um loop automatico em producao.

**Acceptance criteria:**
1. `POST /v1/redmine-sync/processar` DEVE aceitar autenticacao por JWT admin OU
   `X-Service-Token` com escopo `redmine_sync:processar`.
2. DEVE suportar `dry_run` com resposta estruturalmente distinta de uma execucao real
   (nunca simular sucesso identico ao real).
3. NAO DEVE existir loop de polling automatico em background — execucao e sempre explicita
   (decisao deliberada, ver design.md).

## Requirement 2 — Limpeza de reservas travadas antes de novo lote

**User story:** Como operador, quero que reservas intermediarias travadas (worker que morreu
no meio do processamento) sejam limpas automaticamente antes de reservar um novo lote, para
que a fila nao fique permanentemente bloqueada.

**Acceptance criteria:**
1. `limpar_reservas_travadas` DEVE rodar antes de `processar_fila_redmine` reservar novas
   linhas.
2. Timeout padrao de reserva DEVE ser 15 minutos, configuravel via
   `REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS`.
3. Quando uma limpeza ocorrer, DEVE ser registrada em log/auditoria.

*(Este requisito replica a regra global obrigatoria do CLAUDE.md do usuario para fluxos que
reservam registros — nao e especifico deste feature, mas esta implementado aqui.)*

## Requirement 3 — Escrita idempotente e auditavel de volta em Dataverse

**User story:** Como responsavel por compliance, quero que cada tentativa de criar issue no
Redmine grave o resultado (SENT/ERROR) de volta em `RedmineQueue`, `AgileSync` e
`cr85a_auditlog`, para manter rastreabilidade completa do fluxo Planner -> Dataverse -> Redmine.

**Acceptance criteria:**
1. Sucesso DEVE atualizar status para SENT (+ `cr85a_redmineissueid` quando disponivel).
2. Falha DEVE atualizar status para ERROR com detalhe do erro persistido.
3. Toda tentativa (sucesso ou falha) DEVE gerar um evento em `cr85a_auditlog`, correlacionado
   por `correlation_id` (ADR-003).
4. Chamada ao Redmine DEVE reusar retry/circuit-breaker ja existente em `github_redmine.py`
   (nao reimplementar).

## Requirement 4 — Diagnostico do bug de truncamento de CorrelationId

**User story:** Como operador, quero um endpoint que confirme ao vivo se a coluna
`cr85a_agilesync.cr85a_correlationid` tem `MaxLength` suficiente (>=36) antes de eu mexer no
schema do Dataverse manualmente, para nao adivinhar.

**Acceptance criteria:**
1. `GET /v1/redmine-sync/diagnostico/coluna` DEVE consultar a Dataverse Metadata API ao vivo.
2. DEVE sinalizar explicitamente quando `max_length < 36`.

## Requirement 5 — Adapter Dataverse generico e reutilizavel

**User story:** Como desenvolvedor, quero um cliente OData generico para Dataverse (nao
acoplado a uma tabela especifica), para reusar em outras integracoes Dataverse futuras.

**Acceptance criteria:**
1. DEVE resolver `EntitySetName` ao vivo via Metadata API, sem adivinhar pluralizacao.
2. DEVE reusar o mesmo padrao de token client-credentials ja usado em `hub_lowcode.py`
   (`_token_dataverse`), nao duplicar logica de auth.

## Gaps conhecidos (nao inventar como "resolvido")

- Colunas `cr85a_reservedat`, `cr85a_retrycount`, `cr85a_errordetail` sao assumidas como
  necessarias em `cr85a_redminequeue` mas **nao ha confirmacao de que existem** no Dataverse
  real — so o `diagnostico/coluna` confirma isso ao vivo.
- `REDMINE_API_KEY`, `REDMINE_PROJECT_ID`, `REDMINE_SYNC_DATAVERSE_URL` estao vazios no `.env`
  real (verificado em 2026-08-16) — feature nao esta configurada para rodar em producao.
- Nenhum teste end-to-end real contra Dataverse/Redmine foi executado — so testes unitarios
  com mocks.
