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

## O que falta de fato (gap real, não só cadastro de secret)

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
