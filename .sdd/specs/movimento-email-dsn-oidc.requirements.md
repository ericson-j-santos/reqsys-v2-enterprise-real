# Movimento Email DSN — OIDC governado

## Requisito 1 — reutilizar identidade OIDC governada
O workflow `Movimento Email DSN Bootstrap` deve autenticar no Azure por OIDC reutilizando as variáveis de repositório já adotadas pelos fluxos governados do ReqSys: `CCP_AZURE_CLIENT_ID_FLY_GOVERNED_COMMAND`, `CCP_AZURE_TENANT_ID` e `CCP_AZURE_SUBSCRIPTION_ID`.

Não deve ser introduzido `client secret` para substituir OIDC.

## Requisito 2 — falhar fechado antes do login
Antes de `azure/login`, o workflow deve verificar apenas a presença dos parâmetros obrigatórios e interromper a execução quando estiverem ausentes, sem imprimir seus valores.

A validação deve incluir a identidade OIDC e `REQSYS_KEY_VAULT_NAME`.

## Requisito 3 — preservar sigilo do DSN
A alteração de autenticação não pode reduzir os controles existentes: usuário, senha, DSN, tokens e valores recuperados do Key Vault não podem ser publicados em logs, issues ou artefatos de evidência.

## Requisito 4 — preservar o fluxo SQL existente
Após autenticação válida, o fluxo deve continuar instalando ODBC Driver 18, montar o DSN por meio do Key Vault, mascarar o valor e executar o verificador de conexão/estruturas sem mudar o contrato SQL da Prospecção Movimento.

## Requisito 5 — verificador SQL executável de forma independente
O script `scripts/verificar_movimento_email_fontes.py` deve poder executar o comando `status` sem carregar `app.core.config.Settings` nem depender de `pydantic`/`pydantic-settings`. O carregamento de `python-dotenv` pode ser opcional, e a configuração operacional deve ser lida diretamente das variáveis `MOVIMENTO_EMAIL_SOURCE_DSN` e `MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS`.

O valor do DSN nunca deve ser impresso. Timeout ausente, vazio ou inválido deve usar o padrão seguro de 30 segundos.

## Critérios de aceite (Acceptance Criteria)
1. O workflow referencia as três variáveis `CCP_AZURE_*` governadas e não referencia `vars.AZURE_CLIENT_ID`, `vars.AZURE_TENANT_ID` ou `vars.AZURE_SUBSCRIPTION_ID`.
2. `permissions.id-token` permanece `write` e `azure/login@v2` permanece sem `client-secret`.
3. Existe validação fail-closed anterior ao login Azure para os parâmetros obrigatórios, sem impressão de seus valores.
4. O teste contratual `tests/test_movimento_email_dsn_bootstrap_workflow.py` deve passar.
5. O `Pre-PR Readiness Gate` deve retornar `READY_FOR_PR=passed` no SHA exato proposto para a Pull Request.
6. A homologação real do DSN continua bloqueada até servidor, banco e segredos SQL autorizados estarem disponíveis; testes estáticos não podem ser tratados como evidência de conexão real.
7. O comando `status` do verificador deve funcionar sem importar o backend e deve diferenciar DSN ausente de DSN configurado.
8. O teste `tests/test_verificar_movimento_email_fontes.py` deve validar leitura das variáveis, fallback do timeout e não exposição do DSN.
