# Pendência manual — Publicação/ativação Teams v2 no Power Platform DEV

Status: **PENDENTE** (ação humana fora do código)
Data de registro: 2026-07-19
Repositório: `ericson-j-santos/reqsys-v2-enterprise-real`

## Nota original recebida

> Cadastrar 4 Environment secrets (`POWERPLATFORM_DEV_ENVIRONMENT_URL`,
> `POWERPLATFORM_APP_ID`, `POWERPLATFORM_CLIENT_SECRET`, `POWERPLATFORM_TENANT_ID`)
> no environment `powerplatform-development` e executar o workflow
> **Teams Notification DEV Import** (`source_mode=export_dev`,
> `artifact_name=reqsys-teams-notifications-v2-official`,
> `confirmation=IMPORT-REQSYS-TEAMS-V2-DEV`) para importar a solution
> `ReqSysTeamsNotifications` e ativar o flow `robo_envia_teamsv2` em DEV.

## Correções após verificação contra o repositório (2026-07-19)

Checado via `git log`/`grep` no working copy local e via `gh api` contra o
GitHub real. Divergências encontradas em relação à nota original:

| Item da nota original | Estado real verificado |
| --- | --- |
| Environment `powerplatform-development` | **Não existe.** Os 7 environments atuais do repo são: `copilot`, `dev`, `development`, `github-pages`, `production`, `reqsys-power-platform-dev`, `staging`. O environment correto para Power Platform DEV é **`reqsys-power-platform-dev`** (criado em 2026-07-15). |
| Secrets `POWERPLATFORM_DEV_ENVIRONMENT_URL` / `POWERPLATFORM_APP_ID` / `POWERPLATFORM_CLIENT_SECRET` / `POWERPLATFORM_TENANT_ID` | A convenção já usada no repo (workflow `.github/workflows/copilot-hitl-dev-import.yml`) é **`POWER_PLATFORM_ENVIRONMENT_URL`**, **`POWER_PLATFORM_CLIENT_ID`**, **`POWER_PLATFORM_CLIENT_SECRET`**, **`POWER_PLATFORM_TENANT_ID`** (com underscore entre `POWER` e `PLATFORM`). Consultado via `gh api repos/ericson-j-santos/reqsys-v2-enterprise-real/environments/reqsys-power-platform-dev/secrets`: **os 4 já estão cadastrados desde 2026-07-15T01:21** — não é necessário recriá-los, apenas confirmar se o service principal ainda é válido/não expirou. |
| Workflow **Teams Notification DEV Import** | **Não existe no repositório** (confirmado via `gh workflow list --all`, sem correspondência, e via busca por `source_mode`/`artifact_name`/`IMPORT-REQSYS-TEAMS-V2-DEV` em todo o working copy — zero ocorrências). O único workflow de importação DEV existente e análogo é **`Copilot HITL DEV Import`** (`.github/workflows/copilot-hitl-dev-import.yml`), que importa a solution `ReqSysCopilotHITL` (não a `ReqSysTeamsNotifications`) usando `environment: reqsys-power-platform-dev` e confirmação `IMPORT_DEV` (formato diferente do `IMPORT-REQSYS-TEAMS-V2-DEV` citado na nota). |
| Secret adicional não mencionado na nota | `copilot-hitl-dev-import.yml` também depende de `POWER_PLATFORM_DEPLOYMENT_SETTINGS_JSON`, que **não apareceu** na lista de secrets do environment `reqsys-power-platform-dev` (só os 4 acima existem). Se o workflow Teams v2 seguir o mesmo padrão, esse secret também precisará existir. |
| Solution/flow `robo_envia_teamsv2` | O flow de produção documentado em [teams-messaging-gateway.md](../architecture/teams-messaging-gateway.md) é `robo_envia_teams20260108v2` (dentro da solution `robo_envia_mensagem_teams`), não uma solution chamada `ReqSysTeamsNotifications` nem um flow literalmente nomeado `robo_envia_teamsv2`. Pode ser um nome de trabalho para uma solution "oficial" v2 ainda a empacotar — não confirmado nos artefatos do repo. |

## Avaliação: `copilot-hitl-dev-import.yml` serve de modelo?

Comparado linha a linha com o código de provisionamento Teams já existente
(`backend/app/services/teams_flow_bot_provisioning.py`, endpoint
`POST /v1/teams-gateway/flow-bot/promover-solution`, documentado em
[teams-messaging-gateway.md](../architecture/teams-messaging-gateway.md#automacao-o-que-da-e-o-que-nunca-vai-dar)).

**Parte reaproveitável (esqueleto de governança CI):**

- `environment:` fixo no job (gate de Environment secrets/approvers do GitHub).
- Input `confirmation` com string exata obrigatória antes de qualquer ação real.
- `concurrency` (evita duas importações concorrentes).
- Upload de artifact de evidência ao final (sucesso ou falha).

**Parte que NÃO serve — mecanismo de transporte é diferente:**
`copilot-hitl-dev-import.yml` **materializa** um pacote unmanaged a partir de
código Python (`scripts/materialize_copilot_hitl_solution.py`) e importa via
`microsoft/powerplatform-actions/import-solution` (CLI `pac`), usando os
secrets `POWER_PLATFORM_CLIENT_ID` / `POWER_PLATFORM_CLIENT_SECRET` /
`POWER_PLATFORM_TENANT_ID` / `POWER_PLATFORM_ENVIRONMENT_URL`. Isso pressupõe
que a solution é **gerada pelo ReqSys**. Não é o caso do Teams v2: a solution
`ReqSysTeamsNotifications`/flow `robo_envia_teamsv2` (se vier a existir) seria
construída manualmente no Maker Portal, exatamente como já documentado para
`robo_envia_mensagem_teams` — não há gerador de código para ela.

**O que de fato já existe e se encaixa melhor:** o ReqSys já implementa
export→import→vínculo de conexão→ativação via Dataverse Web API
(`exportar_solution`, `importar_solution`, `vincular_connection_reference`,
`obter_workflow_id_por_nome`, `ativar_flow`, orquestrados por
`promover_flow_para_ambiente`), exposto em
`POST /v1/teams-gateway/flow-bot/promover-solution` (`require_admin`). Esse
caminho:

- **Usa credenciais diferentes das do pendência original**: não usa
  `POWER_PLATFORM_*` (secrets de Environment do GitHub) — usa
  `AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET`/`AZURE_TENANT_ID`, já configurados
  no runtime do backend ReqSys (não no GitHub). Ou seja: **se este caminho for
  adotado, os 4 secrets `POWER_PLATFORM_*` do GitHub Environment nem seriam
  necessários** para esta operação específica — bastaria o workflow chamar a
  API do ReqSys com um token admin.
- Exige `environment_url_origem` **e** `environment_url_destino` — não existe
  hoje um modo "só DEV" equivalente ao `source_mode=export_dev` da nota
  original; seria preciso decidir se origem=destino=DEV (reimportar na mesma
  env, cenário atípico) ou se DEV é o destino de uma promoção vinda de outra
  env.
- Exige `connection_id_destino` — o GUID de uma conexão Teams **já autorizada
  interativamente por um humano** no ambiente de destino. Não existe forma de
  obter isso via API; precisa ser coletado manualmente antes de disparar o
  workflow.

**Risco bloqueante encontrado:** o próprio módulo e o runbook de arquitetura
registram que a parte de **escrita** desse fluxo
(`ImportSolution`/`PATCH connectionreferences`/`PATCH workflows`) **nunca foi
validada ao vivo contra o tenant real** (só leitura foi confirmada, em
2026-07-09). Criar um workflow de CI que dispara essa escrita pela primeira
vez em DEV seria o primeiro teste real desse código contra produção — o
próprio doc de arquitetura evitou deliberadamente isso ("para não arriscar
desativá-lo sem necessidade"). Recomendação: validar essa escrita manualmente
uma vez (ambiente controlado, com rollback manual disponível) antes de
automatizar via GitHub Actions, alinhado ao ADR-011 (autonomia exige dry-run e
limite de tentativas antes de produção).

## O que falta de fato (gap real, só cadastro de secret não resolve)

1. **Criar o workflow `Teams Notification DEV Import`** — hoje ele não existe.
   Se for para seguir o padrão já estabelecido, o caminho natural é espelhar
   `.github/workflows/copilot-hitl-dev-import.yml` (mesmo `environment:
   reqsys-power-platform-dev`, mesmo padrão de confirmação obrigatória,
   materialização de solution + `pac solution import` + smoke test), trocando
   os artefatos para a solution/flow do Teams v2.
2. **Confirmar se os 4 secrets já existentes em `reqsys-power-platform-dev`
   ainda são válidos** (não rotacionados/expirados) antes de reusá-los —
   evita assumir que "cadastrar" ainda é necessário quando na verdade é só
   "revalidar".
3. **Definir e empacotar a solution oficial** (`ReqSysTeamsNotifications` ou
   nome definitivo) e o flow correspondente, já que hoje o ambiente Dataverse
   só tem o flow `robo_envia_teams20260108v2` dentro de
   `robo_envia_mensagem_teams`.

## Caminho no GitHub (quando o workflow existir)

```text
Repository → Settings → Environments → reqsys-power-platform-dev → Environment secrets
```

## Segurança

- **Nunca registrar valores de secrets** em issues, PRs, commits, mensagens
  públicas ou neste runbook — apenas nomes de chave.
- Este documento não contém e não deve vir a conter nenhum valor de
  `client_secret`, `tenant_id`, `app_id` ou URL de ambiente real.
- Antes de rodar qualquer importação real em DEV, seguir o guard rail de
  confirmação explícita (`confirmation=...`), igual ao já adotado em
  `copilot-hitl-dev-import.yml`.

## Referências

- [cofre-operacional.md](cofre-operacional.md)
- [teams-messaging-gateway.md](../architecture/teams-messaging-gateway.md)
- `.github/workflows/copilot-hitl-dev-import.yml` (padrão de referência para o novo workflow)
- [ADR-041 — Cofre de segredos locais](../ADR/ADR-041-cofre-segredos-locais.md)
