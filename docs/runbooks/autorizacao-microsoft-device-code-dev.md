# Runbook — autorização Microsoft (Device Code) nos workflows DEV remanescentes

## Escopo atual

O fluxo **Excel → SQL Server → SharePoint** não usa mais Device Code.

Desde a promoção do E2E OIDC para a `main`, essa integração usa:

- GitHub OIDC → Microsoft Entra ID;
- Microsoft Graph para SharePoint;
- Dataverse Web API para leitura, atualização e ativação do flow;
- cleanup determinístico com restauração de `clientdata`, workbook e resíduos de teste.

O workflow canônico é:

`.github/workflows/integration-excel-sql-sharepoint-oidc-dev.yml`

Os workflows históricos de Excel → SQL Server → SharePoint permanecem apenas como wrappers de compatibilidade e reutilizam o workflow OIDC canônico. Eles não devem voltar a invocar `msal_device_code*`, `device_code` ou depender de sessão MSAL delegada.

Evidência de execução real na `main`:

- run `35365623618`;
- source SHA `abf3ea29618c125bb281ef4f7266cf7303c76f0f`;
- `auth_mode=github_oidc_dataverse`;
- aceite funcional `passed`;
- cleanup `passed`.

## Por que este runbook ainda existe

Os módulos compartilhados de Device Code continuam necessários para outras jornadas DEV que ainda exigem autenticação delegada de usuário, atualmente incluindo o aceite **Planner → Teams**.

Enquanto essas jornadas existirem, os arquivos compartilhados:

- `scripts/msal_device_code.mjs`;
- `scripts/msal_device_code_prepare.mjs`;
- `scripts/msal_device_code_complete.mjs`;

não devem ser removidos globalmente.

A remoção definitiva desses módulos só é segura quando uma busca no repositório comprovar ausência de consumidores funcionais além de testes/documentação.

## Comportamento do Device Code nas jornadas remanescentes

`msal_device_code_prepare.mjs` prepara a autorização delegada e `msal_device_code_complete.mjs` aguarda a conclusão. Quando o código expira, o módulo compartilhado pode renovar o código enquanto houver orçamento de espera.

Controles obrigatórios:

- o valor privado `device_code` não é publicado;
- somente `verification_uri` e `user_code` podem aparecer no resumo/log;
- recusa explícita de autorização deve falhar imediatamente;
- refresh token não deve ser persistido em log, artefato ou repositório;
- a sessão deve continuar efêmera, salvo decisão explícita e governada em contrário.

## Procedimento para jornadas que ainda usam Device Code

1. confirme que o workflow realmente é um consumidor atual de `msal_device_code_prepare.mjs` / `msal_device_code_complete.mjs`;
2. dispare o workflow DEV correspondente;
3. acompanhe o Summary do job;
4. abra a URL de verificação exibida e informe o `user_code`;
5. se o código expirar, use o código renovado publicado pelo mesmo run;
6. após a autorização, valide o restante do E2E e a evidência independente do estado final.

## O que não fazer

- não usar este runbook para Excel → SQL Server → SharePoint;
- não reintroduzir Device Code no workflow OIDC canônico;
- não adicionar `auth_wait_minutes` aos wrappers de Excel → SQL Server → SharePoint;
- não persistir token delegado para eliminar o passo humano;
- não apagar os módulos compartilhados enquanto Planner → Teams ou outra jornada ainda os consumir.

## Critério para aposentadoria total do Device Code

A aposentadoria global só está concluída quando:

1. nenhum workflow funcional referencia `msal_device_code_prepare.mjs`, `msal_device_code_complete.mjs` ou `msal_device_code.mjs`;
2. os testes específicos de jornadas migradas comprovam autenticação não interativa;
3. as jornadas migradas possuem E2E real verde com cleanup/restauração quando aplicável;
4. documentação e contratos SDD não instruem mais uso de Device Code;
5. os módulos e testes compartilhados podem então ser removidos em uma PR dedicada, com CI verde.
