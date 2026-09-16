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

## Fluxo

1. valida tenant e aplicação pelo `client_id` já conhecido pelo executor;
2. valida sessão GitHub;
3. deriva nome da credential a partir do `correlation_id`;
4. bloqueia se a mesma rotação já existir;
5. cria password credential aditiva no Entra com validade máxima de 365 dias;
6. mantém `secretText` apenas em memória;
7. envia o valor ao `gh secret set` exclusivamente por `stdin`;
8. relê somente metadados do Environment Secret (`name`/`updated_at`);
9. se a escrita no GitHub falhar, remove a password credential recém-criada;
10. captura o SHA vigente da `main`;
11. dispara `Integration Excel SQL SharePoint — Functional Evidence DEV` na `main`;
12. retorna somente evidência sanitizada.

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

## Evidência de sucesso

A saída deve conter:

- `status=rotated`;
- `environment=reqsys-power-platform-dev`;
- `github_secret.name=POWER_PLATFORM_CLIENT_SECRET`;
- `github_secret.updated_at` preenchido;
- `secret_value_exposed=false`;
- `existing_credentials_deleted=false`;
- `validation.run_id` e `validation.head_sha` quando o dispatch não foi suprimido.

A existência do secret não prova o E2E. O fechamento da issue #1649 continua condicionado ao workflow funcional produzir `functional_evidence=true`, incluindo fonte SQL real, positivo, negativo, idempotência, leitura independente e cleanup.

## Falhas e rollback

- tenant divergente, sessão ausente ou aplicação não localizada: fail-closed antes de mutação;
- mesmo `correlation_id`: `ROTATION_ALREADY_EXISTS`, sem duplicar credential;
- falha no `gh secret set`/verificação: tenta remover imediatamente a credential criada nesta execução;
- falha depois da confirmação do secret no GitHub: mantém a credential para não invalidar o secret recém-gravado e exige reconciliação posterior;
- nenhum caminho imprime `secretText`.
