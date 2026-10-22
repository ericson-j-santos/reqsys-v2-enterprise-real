# Recuperação governada do produtor TODO Global — Azure Key Vault DEV

## Problema
O TODO Global Hourly Cycle do ReqSys falhou no run 39616271178 porque o segredo
reqsys-pc24x7-todo-runtime-producer-token não estava disponível no Azure
Key Vault DEV. O reconciliador legado pode provisioná-lo, mas também aciona
Docker Compose e operações de runtime fora da autorização concedida em 21/10/2026.

## Requisitos
1. Custo adicional máximo R$ 0,00. O primeiro acesso Azure deve ser uma
   consulta ARM exclusivamente de leitura à assinatura configurada.
   `state=Enabled`, `subscriptionPolicies.spendingLimit=On` e `quotaId` válido
   comprovam somente a presença de um hard-stop de estouro de crédito; não
   comprovam preço unitário zero para uma operação Key Vault. `Off`,
   `CurrentPeriodOff`, ausência, HTTP 403 e timeout bloqueiam imediatamente.
   Mesmo com `On`, o data plane permanece bloqueado até existir prova
   autoritativa e vigente de custo literal zero. Budget de alerta não é hard stop.
2. Ler o Key Vault existente somente via ARM para conferir assinatura, tenant,
   grupo de recursos e identidade exata do vault DEV. Não criar vault, alterar
   SKU, conceder RBAC ou acionar recursos pagos.
3. Reutilizar o Authorized Actions Gateway já publicado, na issue operacional
   #1705, aceitando SOMENTE o comentário exato do proprietário:
   /reqsys run todo-producer-keyvault-dev. O Gateway despacha o workflow
   existente todo-global-hourly-cycle.yml em main, com operação tipada
   producer-credit-gated e autorização correlacionada ao comentário. O job
   OIDC deve validar em leitura independente o comentário autorizado
   (autor, issue, comando, ID, prazo) antes de acessar ARM/Key Vault.
   OIDC limitado a DEV, permissões contents:read, issues:read, id-token:write
   exclusivamente no job, executor ubuntu-24.04 do repositório público.
   Não aumentar a quantidade de workflows do ReqSys. Dispatch manual de
   `cycle` e `reconcile-runtime` aceita somente o owner. O bot permanece aceito
   apenas em `producer-credit-gated`, vinculado ao comentário revalidado; uma
   futura reabertura ao bot exige binding equivalente de comment_id e comando.
4. Nenhuma operação do data plane Key Vault pode decorrer apenas da observação
   ARM de `spendingLimit=On`. Registrar `AZURE_SPENDING_LIMIT_ON_CONFIRMED`,
   `literal_zero_cost_verified=false` e `keyvault_data_plane_allowed=false`;
   bloquear antes da primeira consulta ao segredo. Inputs de dispatch, secrets,
   vars e ambiente não podem promover essa decisão. O mesmo bloqueio antecede
   o reconciliador por SDK e é repetido no export público do token.
5. Somente após futura prova autoritativa de custo literal zero: se o segredo
   estiver ativo/habilitado, reutilizar sem set/recover; se soft-deleted,
   recuperar a mesma identidade; se ausente, criar somente o segredo produtor
   DEV, gerado criptograficamente em arquivo efêmero 0600, nunca em argumento
   de processo nem log. Não existe essa prova no contrato atual.
6. Erros de permissão, segredo desabilitado, resposta inesperada, vault
   divergente e custo desconhecido resultam em bloqueio sem bypass.
7. Evidência sanitizada distingue ACTIVE_ALREADY_PRESENT,
   RECOVERED_RUNTIME_BINDING_UNVERIFIED e PROVISIONED_RUNTIME_BINDING_PENDING.
   A criação não oferece compare-and-swap atômico; verificar ausência novamente
   e serializar o workflow, sem alegar atomicidade absoluta. Confirmar metadata
   readback; nunca coletar ou publicar valores do segredo.
8. Confirmar segredo NÃO comprova associação ao serviço em execução.
   Não executar Docker, restart, deploy ou promoção. TODO-38 e TODO-30 permanecem
   EM ANDAMENTO / E2E PARCIAL até testes reais completos.
9. Preservar idempotency_key e correlation_id do TODO Global e registrar SHA
   e run do workflow; não despachar nova tarefa de produto.
10. Testes offline de script, CLI e workflow: subscrição On/Off, id/ator,
    `GITHUB_WORKFLOW_REF`/`GITHUB_WORKFLOW_SHA`, vault, token canônico, rejeição
    de CR/LF/NUL, ativo, soft-delete, provisionamento por arquivo privado, RBAC
    negado, idempotência e zero operação Key Vault quando não há prova de custo
    literal zero.

## Critérios de aceite
- READY_FOR_PR=passed no SHA vigente, antes de abrir PR.
- CI do PR terminal no HEAD e sem falhas; merge somente governado.
- Após integração, um único comando exato do owner na issue operacional #1705,
  com comment_id vinculado ao workflow_dispatch; manter issue #2973 como fonte
  do escopo autorizado.
- Se spendingLimit não é On: COST_UNKNOWN_BLOCKED sem operações data-plane.
- Se spendingLimit é On: registrar somente o hard-stop observado e retornar
  KEYVAULT_DATA_PLANE_BLOCKED enquanto `literal_zero_cost_verified=false`.
- Um receipt observacional de hard-stop não autoriza recuperação, criação nem
  leitura do segredo. Não existe autorização de data plane no estado atual.
- Nenhum E2E de produto declarado antes de jornada real DEV, leitura por ID
  e replay negativo sem duplicidade.

## Referências
- Run 39616271178: SecretNotFound.
- Issue #2973, comentário 6319619092: autorização técnica de credencial DEV.
- Issue #1705: Authorized Actions Gateway existente, rota exata e SHA em main.
- chatgpt-operational-rules/rules/cost-governance.md.
- Microsoft ARM REST Subscriptions/Get API 2022-12-01: spendingLimit.


## Prevenção de cobranças recorrentes no ciclo horário (21/10/2026)
O ciclo agendado falhou no run 39642465391 após tentar obter diretamente o token
no Key Vault, mesmo depois de a prova manual 39642269836 ter confirmado
`COST_UNKNOWN_BLOCKED` (sem `spendingLimit=On`). O job `cycle` deve executar
a mesma consulta ARM somente leitura, vinculada à main, ao arquivo exato do
workflow e ao SHA do workflow. `Off`, `CurrentPeriodOff`, erro ARM,
tenant/vault incompatíveis, branch indevida ou identidade divergente bloqueiam.
`On` produz apenas `AZURE_SPENDING_LIMIT_ON_CONFIRMED`; como não há prova de
custo literal zero, o helper retorna `KEYVAULT_DATA_PLANE_BLOCKED` antes de
`az keyvault secret show`. Nunca marcar a rotina como E2E aprovada por sucesso
de login Azure ou de contrato. O gate não modifica o estado do TODO-38.
