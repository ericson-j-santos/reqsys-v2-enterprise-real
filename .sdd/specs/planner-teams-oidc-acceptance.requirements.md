# Planner → Teams DEV — Acceptance via GitHub OIDC

## Requisito 1 — autenticação não interativa
O acceptance DEV deve usar GitHub OIDC / Workload Identity Federation e não pode depender de Device Code, refresh token, sessão MSAL delegada ou client secret para Microsoft Graph.

## Requisito 2 — reutilização do E2E canônico
O workflow `planner-teams-notify-dev-acceptance.yml` deve reutilizar `runtime-e2e-continuous.yml` por `workflow_call`, evitando duas implementações divergentes do mesmo teste.

## Requisito 3 — prova real
O E2E deve criar duas tarefas reais no Planner:
- tarefa `REQSYS-E2E-*`: controle negativo, não deve produzir mensagem no Teams;
- tarefa normal: controle positivo, deve produzir mensagem no Teams.

A validação do efeito deve ocorrer por leitura independente do canal Teams via Microsoft Graph.

## Requisito 4 — cleanup
As tarefas criadas pelo E2E devem ser removidas ao final. Falha de cleanup mantém o run vermelho.

## Requisito 5 — segurança
Tokens OIDC são efêmeros e mascarados. Nenhum token, Device Code, refresh token ou segredo Microsoft é publicado em artifact, Summary ou log.

## Requisito 6 — compatibilidade
O nome histórico `Planner Teams Notify DEV Acceptance` permanece disponível por `workflow_dispatch`, mas delega integralmente ao Runtime E2E OIDC.

## Critérios de aceite
1. O acceptance não contém `msal_device_code`, `device_code`, `WSJF_MSAL_STORAGE_STATE_B64` ou `POWER_PLATFORM_CLIENT_SECRET`.
2. O Runtime E2E expõe `workflow_call`.
3. Os testes de contrato OIDC passam.
4. O E2E real Planner→Teams retorna `status=passed`, `auth_mode=oidc`, CT-01 negativo, CT-02 positivo e cleanup concluído.
5. Os módulos Device Code são removidos somente após busca confirmar ausência de consumidores ativos.

## Requisito 7 — flows ativos
Antes de criar tarefas de prova, o E2E deve localizar os dois flows Planner→Teams no Dataverse, validar as referências `shared_planner` e `shared_teams`, ativar somente quando necessário e confirmar `statecode=1/statuscode=2` sem alterar o `clientdata`.

