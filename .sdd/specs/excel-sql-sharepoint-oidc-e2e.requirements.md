# Excel → SQL Server → SharePoint via OIDC — Requisitos

## Requisito 1 — autenticação não interativa
O E2E DEV deve autenticar o GitHub Actions no Microsoft Entra ID por OIDC, sem Device Code, senha, client secret ou refresh token persistido.

## Requisito 2 — gerenciamento suportado do fluxo
A descoberta do SharePoint deve usar Microsoft Graph e o gerenciamento do fluxo deve usar Dataverse Web API. A solução não deve depender da API não suportada `api.flow.microsoft.com` para provisionar ou ativar o fluxo.

## Requisito 3 — integração real e rastreável
O aceite deve executar Excel real → fluxo Power Automate → SQL Server real via gateway → SharePoint, preservando `correlation_id`, SHA de origem e leitura independente do destino.

## Requisito 4 — caso negativo e idempotência
Um identificador inválido não pode gerar saída válida. A repetição do identificador válido deve atualizar o mesmo item lógico, sem criar duplicidade.

## Requisito 5 — cleanup determinístico
O workflow deve capturar o estado original antes da mutação e executar cleanup em passo independente mesmo quando o aceite falhar. O cleanup deve:
- desligar o fluxo e confirmar `statecode=0`;
- restaurar o `clientdata` original e validar hash;
- restaurar o workbook pela versão histórica original, tolerando lock transitório `423`;
- remover resíduos da correlação no SharePoint;
- validar por leitura independente o estado final restaurado.

## Requisito 6 — concorrência segura
Execuções do E2E DEV devem ser serializadas sem cancelar uma execução em andamento, para que o cleanup tenha oportunidade de terminar.

## Critérios de aceite (Acceptance Criteria)
1. Os testes de OIDC/Dataverse, descoberta, fluxo e cleanup mapeados no SDD passam.
2. O workflow usa `id-token: write` e `azure/login@v2`, sem Device Code.
3. O E2E real comprova caso positivo, caso negativo e idempotência.
4. O cleanup comprova fluxo desligado, `clientdata` restaurado, workbook restaurado por hash e ausência de resíduo SharePoint.
5. A concorrência do workflow usa fila com `cancel-in-progress: false`.
6. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato com `behind_by=0`.


## Requisito 7 — canonicidade operacional
O workflow OIDC deve ser o caminho automático de DEV na `main`, aceitar `workflow_dispatch` e `workflow_call`. Os workflows históricos de E2E e evidência funcional devem preservar seus nomes/checks apenas como wrappers de compatibilidade e reutilizar o workflow OIDC canônico.

## Requisito 8 — retirada do Device Code desta integração
Nenhum workflow Excel → SQL Server → SharePoint pode invocar `msal_device_code`, `device_code` ou depender de sessão MSAL delegada. Após a migração OIDC das demais jornadas consumidoras, os módulos `msal_device_code_*` e o normalizador `normalize_msal_storage_state.py` devem estar ausentes do repositório.

## Critérios adicionais de aceite
7. O teste de contrato comprova `workflow_dispatch` + `push` na `main` + `workflow_call` no workflow OIDC.
8. O alias manual e o workflow de evidência funcional chamam `integration-excel-sql-sharepoint-oidc-dev.yml`, usam `secrets: inherit` e não contêm referências a Device Code.
9. Contratos de captura SQL em modo `power_platform_gateway` deferem a validação real para `integration-excel-sql-sharepoint-oidc-dev.yml`.

10. O repositório não contém `msal_device_code_*` nem `normalize_msal_storage_state.py`.
