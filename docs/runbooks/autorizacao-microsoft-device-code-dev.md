# Runbook — autorização Microsoft (device code) nos workflows DEV

## Por que existe um passo humano

O E2E `Excel → SQL Server → SharePoint` invoca o flow do Power Automate em
`https://service.flow.microsoft.com` e lista ambientes/conexões em
`https://api.powerplatform.com`. Esses dois escopos são exercidos com **token delegado**
(usuário), não com o `client_credentials` da aplicação — que no repositório cobre apenas o
Microsoft Graph. Por isso a execução depende de uma autorização interativa da conta
proprietária; não há caminho app-only equivalente para invocar um flow de usuário.

A sessão continua **efêmera**: o refresh token renovado fica somente no runner
(`chmod 600`), não é persistido em secret e não aparece em log, resumo ou artefato.

## O que falhava antes

`msal_device_code_prepare.mjs` pedia um device code no início do job. Se a pessoa não
digitasse o código dentro da validade do Entra ID (~15 min), `msal_device_code_complete.mjs`
encerrava com `device_code_expirado_sem_autorizacao` e o run inteiro era perdido — mesmo
havendo orçamento de tempo sobrando no job.

Evidência do modo de falha: run `35161800221` (SHA `01061aa`), janela aberta às 23:20:26Z e
encerrada às 23:35:29Z sem autorização.

## Comportamento atual

`msal_device_code_complete.mjs` renova o device code sempre que ele expira, até esgotar o
orçamento total de espera:

- cada código renovado é publicado no **resumo do job** (`GITHUB_STEP_SUMMARY`) e como
  `::notice::` no log — a pessoa não precisa rebaixar artefato nem reiniciar o run;
- o arquivo público `device-login.json` é reescrito com `attempt` incremental;
- `device_code` (valor privado) nunca é publicado; só `verification_uri` e `user_code`;
- teto de `MAX_DEVICE_CODE_ATTEMPTS = 6` renovações e nenhum código novo é gerado quando o
  orçamento restante é menor que o intervalo de polling;
- `authorization_declined` continua falhando na hora — recusa explícita não vira renovação.

## Como configurar a janela

`workflow_dispatch` do workflow `Integration Excel SQL SharePoint — Functional Evidence DEV`
aceita `auth_wait_minutes` (padrão `25`). O script normaliza o valor para o intervalo
suportado (300 s a 3000 s), então minutos fora de 5–50 são ajustados em vez de quebrarem o
run. Sem o input (por exemplo, no gatilho de `pull_request`), o padrão é 900 s — o mesmo
comportamento efetivo de antes.

O `timeout-minutes` do job passou para 60 para comportar a janela de autorização mais a
execução do E2E (`--wait-seconds 420`).

## Procedimento

1. dispare o workflow na `main` corrente informando `auth_wait_minutes` conforme a sua
   disponibilidade;
2. abra a página do run e acompanhe o **Summary**;
3. ao ver `Autorização Microsoft necessária`, abra `https://microsoft.com/devicelogin` e
   informe o `user_code` exibido;
4. se o código expirar, aguarde o bloco `código renovado (tentativa N)` no mesmo Summary e
   use o novo código;
5. após a autorização, o job segue sozinho: discovery → candidato real → readiness estrito →
   E2E → leitura independente → gate final.

## O que continua fora de automação

- a autorização interativa em si (credencial + MFA da conta proprietária);
- a existência dos recursos DEV (site/workbook SharePoint, conexões Power Platform,
  procedure SQL real de negócio);
- qualquer decisão de tornar a sessão persistente — isso mudaria a postura de segurança
  atual (`session_persisted: false`) e exige autorização explícita do proprietário.
