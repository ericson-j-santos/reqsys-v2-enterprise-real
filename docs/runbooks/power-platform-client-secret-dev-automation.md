# Automação do `POWER_PLATFORM_CLIENT_SECRET` — DEV

## Objetivo

Eliminar a cópia manual de client secret entre Microsoft Entra e GitHub no fluxo Excel → SQL Server → SharePoint da issue #1649.

A automação é restrita ao GitHub Environment `reqsys-power-platform-dev` e ao secret `POWER_PLATFORM_CLIENT_SECRET`.

## Executor

Executar pelo runtime PC24x7/Command Gateway com:

- sessão `az` já autenticada no tenant correto;
- `gh` já autenticado com acesso ao repositório;
- permissão Entra suficiente para `applications/{id}/addPassword` na aplicação alvo;
- acesso para escrever secrets no GitHub Environment DEV.

Senha, MFA, token e client secret não são aceitos como argumentos.

A operação é Risk 3. O gateway padrão permanece fail-closed; a execução real deve usar a exceção local do proprietário prevista em `chatgpt-operational-rules`, com `action_id`, escopo, expiração e fingerprint previamente allowlisted na máquina ou o modo DEV temporário vigente e auditado quando aplicável. A configuração privada não é criada nem alterada pelo próprio script.

## Fluxo

1. valida tenant e aplicação pelo `client_id` já conhecido pelo executor;
2. valida sessão GitHub;
3. deriva nome da credential a partir do `correlation_id`;
4. bloqueia se a mesma rotação já existir;
5. cria password credential aditiva no Entra com validade máxima de 365 dias;
6. mantém `secretText` apenas em memória;
7. envia o valor ao `gh secret set` exclusivamente por `stdin`, com `stdout` e `stderr` descartados;
8. relê somente metadados do Environment Secret (`name`/`updated_at`);
9. se a escrita/verificação no GitHub falhar, remove a password credential recém-criada;
10. captura o SHA vigente da `main`;
11. dispara `Integration Excel SQL SharePoint — Functional Evidence DEV` na `main`;
12. emite ao terminal somente um envelope sanitizado de status, sem serializar o objeto interno da execução nem mensagens brutas de provedor.

A automação não remove credenciais Entra preexistentes. A limpeza de credenciais antigas depende de comprovação de não uso.

## Dry-run

```text
python scripts/bootstrap_power_platform_client_secret_dev.py \
  --confirm ROTATE-POWER-PLATFORM-CLIENT-SECRET-DEV \
  --tenant-id <tenant-id> \
  --client-id <application-id> \
  --correlation-id issue1649-client-secret-YYYYMMDD-1 \
  --dry-run
```

`tenant-id` e `application-id` são identificadores, não segredos. Não colocar secret, password ou token na linha de comando.

## Execução real

Remover somente `--dry-run`. O padrão cria credential com validade de 90 dias e dispara automaticamente o workflow funcional DEV.

Para uma rotação controlada sem disparar imediatamente o E2E, usar `--skip-validation-dispatch`.

## Saída pública e evidência

O `stdout` da CLI é deliberadamente mínimo:

- `status=rotated`, `dry_run` ou `blocked`;
- `environment=reqsys-power-platform-dev`;
- `secret_value_exposed=false`;
- em bloqueio, `reason` pertence a uma lista fechada de códigos sanitizados, como `azure_session_missing`, `tenant_mismatch`, `entra_application_not_found`, `azure_cli_missing`, `github_cli_missing`, `azure_command_failed`, `github_command_failed`, `github_secret_write_failed`, `validation_workflow_run_not_found`, `rotation_already_exists` ou o fallback `rotation_not_performed`.

Detalhes brutos retornados por Azure/GitHub nunca são serializados no envelope público. Causas não reconhecidas continuam reduzidas a `rotation_not_performed`.

O processo que manipulou o segredo **não** imprime `application_name`, `credential_key`, `github_secret.updated_at`, run ID, URL, SHA ou mensagens brutas de provedor. Após `status=rotated`, esses fatos devem ser comprovados por fontes independentes e não sensíveis:

1. releitura do metadado do Environment Secret confirma `name=POWER_PLATFORM_CLIENT_SECRET` e `updated_at` recente, sem ler o valor;
2. releitura do workflow confirma um novo run de `Integration Excel SQL SharePoint — Functional Evidence DEV` no SHA esperado da `main`;
3. o audit log do Owner Risk 3 registra somente hashes, `action_id`, ambiente, retorno e `correlation_id`, sem `stdout`/`stderr`.

A existência do secret não prova o E2E. O fechamento da issue #1649 continua condicionado ao workflow funcional produzir `functional_evidence=true`, incluindo fonte SQL real, positivo, negativo, idempotência, leitura independente e cleanup.

## Falhas e rollback

- tenant divergente, sessão ausente ou aplicação não localizada: fail-closed antes de mutação e código público sanitizado;
- mesmo `correlation_id`: `rotation_already_exists`, sem duplicar credential;
- falha no `gh secret set`/verificação: tenta remover imediatamente a credential criada nesta execução;
- se o rollback também falhar, a saída pública continua sanitizada e a execução termina bloqueada;
- falha depois da confirmação do secret no GitHub: mantém a credential para não invalidar o secret recém-gravado e exige reconciliação posterior;
- nenhum caminho imprime `secretText`, token, senha ou detalhe bruto de erro de operação sensível.
