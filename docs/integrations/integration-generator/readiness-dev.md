# Readiness DEV — Excel → SQL Server → SharePoint

Este preflight existe para impedir falso positivo antes do E2E real do perfil `excel_sql_sharepoint_sync`.

## O que ele valida

- ambiente restrito a DEV;
- autenticação Microsoft Graph com credencial já provisionada;
- leitura real dos metadados do arquivo Excel alvo;
- leitura real dos metadados da lista SharePoint alvo;
- conectividade real com SQL Server;
- existência da stored procedure configurada;
- presença das referências das três conexões Power Automate;
- evidência vinculada a `source_sha` e `correlation_id`.

## Configuração esperada no ambiente GitHub `reqsys-power-platform-dev`

Segredos, nunca versionados:

- `POWER_PLATFORM_TENANT_ID`;
- `POWER_PLATFORM_CLIENT_ID`;
- `POWER_PLATFORM_CLIENT_SECRET`;
- `INTEGRATION_E2E_SQL_DSN`.

Variáveis não secretas:

- `INTEGRATION_E2E_DRIVE_ID`;
- `INTEGRATION_E2E_FILE_ID`;
- `INTEGRATION_E2E_SITE_ID`;
- `INTEGRATION_E2E_LIST_ID`;
- `INTEGRATION_E2E_SQL_PROCEDURE`;
- `INTEGRATION_E2E_POWER_PLATFORM_ENVIRONMENT_ID`;
- `INTEGRATION_E2E_EXCEL_CONNECTION_ID`;
- `INTEGRATION_E2E_SQL_CONNECTION_ID`;
- `INTEGRATION_E2E_SHAREPOINT_CONNECTION_ID`.

## Modos

No `push` para `main`, o workflow executa em modo relatório para produzir diagnóstico sem transformar ausência de provisionamento em falso defeito do código.

No `workflow_dispatch`, `strict=true` faz o preflight falhar se qualquer dependência real estiver ausente ou inacessível.

## O que não conta como E2E concluído

Readiness verde não prova o fluxo de negócio. Depois do preflight verde ainda é obrigatório executar o fluxo real com:

1. identificador válido e conhecido;
2. identificador inválido como controle negativo;
3. leitura independente no SharePoint pelo marcador da execução;
4. repetição da entrada válida e comprovação de ausência de duplicata;
5. vínculo das evidências ao mesmo ambiente, SHA e `correlation_id`.
