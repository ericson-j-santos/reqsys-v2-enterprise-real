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

## Descoberta automática no `workflow_dispatch`

A execução manual do workflow `Integration Excel SQL SharePoint — DEV E2E` não exige mais copiar manualmente os nove identificadores não secretos.

O passo `Descobrir referências não secretas DEV` resolve em tempo de execução:

- `INTEGRATION_E2E_DRIVE_ID`;
- `INTEGRATION_E2E_FILE_ID`;
- `INTEGRATION_E2E_SITE_ID`;
- `INTEGRATION_E2E_LIST_ID`;
- `INTEGRATION_E2E_SQL_PROCEDURE`, a partir do contrato versionado do perfil;
- `INTEGRATION_E2E_POWER_PLATFORM_ENVIRONMENT_ID`;
- `INTEGRATION_E2E_EXCEL_CONNECTION_ID`;
- `INTEGRATION_E2E_SQL_CONNECTION_ID`;
- `INTEGRATION_E2E_SHAREPOINT_CONNECTION_ID`.

A descoberta usa o contrato do perfil como restrição verificável:

- workbook que contenha a tabela `tbEntrada`;
- lista SharePoint `ResultadoConsulta`;
- ambiente Power Platform classificado como DEV/teste e nunca PROD;
- conexões saudáveis dos conectores `shared_excelonlinebusiness`, `shared_sql` e `shared_sharepointonline`.

Os valores resolvidos são gravados somente no arquivo efêmero `$GITHUB_ENV` do job. O artefato `discovery.json` registra os nomes das variáveis e hashes dos valores, sem publicar os IDs privados.

Se houver mais de um candidato, a descoberta falha fechada. O `workflow_dispatch` oferece dicas opcionais por nome/URL (`site_hint`, `file_hint`, ambiente e conexões) apenas para desambiguar, sem exigir IDs.

## Segredo que continua obrigatório

`INTEGRATION_E2E_SQL_DSN` permanece como GitHub Environment Secret em `reqsys-power-platform-dev`. Ele não é inferido nem impresso porque contém material de conectividade/autenticação do SQL Server.

Também permanecem os segredos Microsoft já provisionados:

- `POWER_PLATFORM_TENANT_ID`;
- `POWER_PLATFORM_CLIENT_ID`;
- `POWER_PLATFORM_CLIENT_SECRET`;
- `WSJF_MSAL_STORAGE_STATE_B64` para a sessão delegada usada no Power Platform.

## Compatibilidade com variáveis persistidas

Em execuções `push` sobre `main`, o workflow continua aceitando as variáveis `INTEGRATION_E2E_*` persistidas no environment para produzir diagnóstico de readiness sem executar o E2E real. No `workflow_dispatch`, os valores descobertos em runtime têm o objetivo de eliminar a cópia manual desses identificadores.

## Modos

No `push` para `main`, o workflow executa em modo relatório para produzir diagnóstico sem transformar ausência de provisionamento em falso defeito do código.

No `workflow_dispatch`, `strict=true` faz o preflight falhar se qualquer dependência real estiver ausente ou inacessível. O E2E só é iniciado depois do readiness verde no mesmo SHA e `correlation_id`.

## O que não conta como E2E concluído

Readiness verde não prova o fluxo de negócio. Depois do preflight verde ainda é obrigatório executar o fluxo real com:

1. identificador válido e conhecido;
2. identificador inválido como controle negativo;
3. leitura independente no SharePoint pelo marcador da execução;
4. repetição da entrada válida e comprovação de ausência de duplicata;
5. vínculo das evidências ao mesmo ambiente, SHA e `correlation_id`;
6. restauração do workbook por hash e remoção do item temporário.
