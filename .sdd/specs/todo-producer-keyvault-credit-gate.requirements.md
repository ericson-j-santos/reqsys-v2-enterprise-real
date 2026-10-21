# Recuperação governada do produtor TODO Global — Azure Key Vault DEV

## Problema
O TODO Global Hourly Cycle do ReqSys falhou no run 39616271178 porque o segredo
reqsys-pc24x7-todo-runtime-producer-token não estava disponível no Azure
Key Vault DEV. O reconciliador legado pode provisioná-lo, mas também aciona
Docker Compose e operações de runtime fora da autorização concedida em 21/10/2026.

## Requisitos
1. Custo adicional máximo R$ 0,00. O primeiro acesso Azure deve ser uma
   consulta ARM exclusivamente de leitura à assinatura configurada.
   Exigir state=Enabled, subscriptionPolicies.spendingLimit=On e quotaId válido;
   Off, CurrentPeriodOff, ausência, HTTP 403 e timeout bloqueiam operações
   tarifáveis do Key Vault. Budget de alerta não é hard stop.
2. Ler o Key Vault existente somente via ARM para conferir assinatura, tenant,
   grupo de recursos e identidade exata do vault DEV. Não criar vault, alterar
   SKU, conceder RBAC ou acionar recursos pagos.
3. Workflow GitHub Actions apenas por issue_comment exato:
   /reqsys recover-todo-producer-keyvault-dev na issue #2973, enviado pelo
   proprietário e recebido em main. OIDC limitado ao job DEV, permissões
   contents:read e id-token:write, executor ubuntu-24.04 padrão do repo público.
4. Nenhuma operação do data plane Key Vault antes da comprovação ARM de custo
   zero; revalidar subscriptionPolicies antes de qualquer consulta ao segredo.
5. Se segredo ativo/habilitado, reutilizar sem set/recover. Se soft-deleted,
   recuperar a mesma identidade. Se ausente, criar somente o segredo produtor
   DEV, gerado criptograficamente em arquivo efêmero 0600, nunca em argumento
   de processo nem log.
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
10. Testes offline de script e workflow: subscrição On/Off, id/ator, vault,
    ativo, soft-delete, provisionamento por arquivo privado, RBAC negado,
    idempotência e nenhuma operação de segredo quando custo falha.

## Critérios de aceite
- READY_FOR_PR=passed no SHA vigente, antes de abrir PR.
- CI do PR terminal no HEAD e sem falhas; merge somente governado.
- Após integração, um único comando exato do owner na issue #2973.
- Se spendingLimit não é On: COST_UNKNOWN_BLOCKED sem operações data-plane.
- Se custo autorizado: somente recuperação/criação do segredo DEV sem valores
  em log/artifact; binding/runtime E2E continua pendente.
- Nenhum E2E de produto declarado antes de jornada real DEV, leitura por ID
  e replay negativo sem duplicidade.

## Referências
- Run 39616271178: SecretNotFound.
- Issue #2973, comentário 6319619092: autorização técnica de credencial DEV.
- chatgpt-operational-rules/rules/cost-governance.md.
- Microsoft ARM REST Subscriptions/Get API 2022-12-01: spendingLimit.
