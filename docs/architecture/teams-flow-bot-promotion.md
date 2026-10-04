# Teams Flow Bot Promotion — conectar `promover_solution` a um workflow real

## Decisão

O backend já expõe `POST /v1/teams-gateway/flow-bot/promover-solution`
(`backend/app/api/teams_gateway.py:313`, serviço
`promover_flow_para_ambiente` em `backend/app/services/teams_flow_bot_provisioning.py:386`,
16 testes) para promover o flow `robo_envia_teamsv2` de um ambiente Power Platform para
outro (`environment_url_origem` → `environment_url_destino`, ex.: dev → test → prod), via
Dataverse ExportSolution/ImportSolution. Essa capacidade existia pronta e testada, mas
**nenhum workflow ou script no repositório a chamava** — ficou desconectada do pipeline real.

Esse endpoint é diferente do que `teams-notification-dev-import.yml` resolve: aquele
workflow captura um pacote (export do próprio DEV, ou artifact de uma run anterior) e
importa **no mesmo ambiente DEV**, via `microsoft/powerplatform-actions` oficial — não tem
conceito de "ambiente de origem" distinto. Não faz sentido religar `promover_solution` a
ele. O gap real era a ausência de um workflow de **promoção entre ambientes** (dev → próximo
ambiente), que é o que este documento cobre.

```text
reqsys-power-platform-dev (origem, POWER_PLATFORM_ENVIRONMENT_URL)
        │
        │  workflow_dispatch: teams-flow-bot-promotion.yml
        │  environment_url_destino, connection_id_destino (pré-autorizado manualmente),
        │  connection_reference_logical_name, ambiente_logico (test|prod)
        ▼
POST /v1/teams-gateway/flow-bot/promover-solution
  Authorization: X-Service-Token (scope teams_gateway:promover_solution)
        │
        │  exportar_solution(origem) → importar_solution(destino) →
        │  vincular_connection_reference(destino) → ativar_flow(destino)
        ▼
Dataverse (ambiente destino): solution importada, connection vinculada, flow ativo
```

## Estado atual x alvo x gaps (ADR-012)

| Item | Estado |
|---|---|
| `POST /v1/teams-gateway/flow-bot/promover-solution` (backend) | ✅ Já existia, testado (16/16) |
| Workflow `teams-flow-bot-promotion.yml` (chama o endpoint acima) | ✅ Implementado nesta entrega |
| Gate de confirmação (`PROMOVER-TEAMS-FLOW-BOT`) | ✅ Implementado |
| Gate extra para `ambiente_logico=prod` (`APROVO-PROMOCAO-PROD`) | ✅ Implementado, espelha `approve_prod_deploy` de `fly-environment-homologation-gate.yml` |
| Validação fail-closed de secrets antes de chamar a API | ✅ Implementado |
| Evidência JSON (manifesto + resultado) como artifact | ✅ Implementado |
| Comentário automático em issue (opcional, via `issue_number`) | ✅ Implementado |
| `REQSYS_API_SERVICE_TOKEN` no environment `reqsys-power-platform-dev` | ⛔ **Não existe** — confirmado via `gh secret list --env reqsys-power-platform-dev` em 2026-08-16. Bloqueador para rodar. |
| Ambiente Power Platform de destino (test/stg ou prod) | ⛔ **Não existe nenhum configurado no GitHub** — só `reqsys-power-platform-dev` tem secrets. Nenhum environment `staging`/`stg`/`production` tem Power Platform credentials. |
| Registro versionado de ambientes (`config/power-platform/environments.json`) + guarda de divergência no workflow | ✅ Implementado — inputs do `workflow_dispatch` são conferidos contra o registro revisado por PR antes de promover. Ver `docs/runbooks/acoes-humanas-power-platform.md` |
| `connection_id_destino` pré-autorizado no ambiente de destino | ⛔ Pré-requisito manual inevitável (ver docstring do endpoint) — precisa de um humano logado no Power Platform do ambiente destino autorizando a conexão Teams antes de disparar este workflow |
| Execução real ponta a ponta | ⏳ **Nunca testado** — este workflow nunca foi disparado |

## Como mintar o `REQSYS_API_SERVICE_TOKEN` quando for a hora

1. Login humano real como admin em `reqsys-api-dev.fly.dev` (login demo também serve — ver
   nota abaixo — ou Azure AD/certificado).
2. `POST /v1/admin/service-tokens` com JWT admin, payload
   `{"label": "...", "scopes": ["teams_gateway:promover_solution"]}`. O token em claro só é
   retornado nessa chamada.
3. `gh secret set REQSYS_API_SERVICE_TOKEN --env reqsys-power-platform-dev` — nunca colar o
   valor em chat, issue, PR ou commit.

**Nota sobre login demo:** `backend/fly.dev.toml` tem `ALLOW_DEMO_LOGIN = "true"`
explicitamente, desde a criação original dos 3 ambientes Fly — é intencional, não uma falha
de segurança. A validação de ambiente (`backend/app/core/config.py:298`) só proíbe isso em
produção (`backend/fly.toml` tem `ALLOW_DEMO_LOGIN = "false"`).

## Como disparar (quando os gaps acima estiverem fechados)

GitHub → Actions → **Teams Flow Bot Promotion** → Run workflow:

```text
ambiente_logico:                    test (ou prod, com approve_producao preenchido)
environment_url_destino:            <URL do ambiente Power Platform de destino>
connection_id_destino:              <connection ID pré-autorizado manualmente no destino>
connection_reference_logical_name:  <nome lógico da connection reference na solution>
solution_name:                      robo_envia_teamsv2
novo_flow_display_name:             robo_envia_teamsv2
managed:                            true
confirmation:                       PROMOVER-TEAMS-FLOW-BOT
approve_producao:                   APROVO-PROMOCAO-PROD  (só se ambiente_logico=prod)
issue_number:                       <opcional>
```
