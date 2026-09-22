# Governança de identidade de aplicação e rotação de tokens

## Estado alvo

Toda integração autenticada deve resolver a identidade por três dimensões obrigatórias:

1. ambiente (`development`, `staging`, `production`);
2. finalidade da integração (`purpose`);
3. classificação dos dados (`public`, `internal`, `confidential`, `restricted`).

A resolução é **fail-closed**. Se não existir exatamente um perfil compatível, a operação deve ser bloqueada.

## App Registration correta por tipo de dado

Para dados `confidential` ou `restricted`, uma mesma `client_id` não pode ser compartilhada entre finalidades distintas. Cada contexto protegido deve possuir App Registration dedicada, com permissões mínimas necessárias.

A configuração existente do ReqSys já separa parcialmente a identidade de login (`AZURE_CLIENT_ID`) da identidade do Teams Bot (`TEAMS_BOT_APP_ID`). O novo registro torna essa segregação uma política validável para os próximos conectores.

## Rotação

Cada perfil possui dois slots de referência de segredo:

- `current_secret_ref`: credencial atualmente ativa;
- `next_secret_ref`: próxima credencial provisionada para rotação.

Segredos em claro são proibidos no catálogo. Os campos devem apontar para um provedor de segredo, por exemplo `vault://`, `keyvault://`, `github-secret://` ou `env://`.

`rotated_at` registra o instante da última rotação e `max_age_days` define a validade máxima, limitada pela implementação a 90 dias. A recomendação operacional padrão é 60 dias, com janela de alerta de 14 dias.

Quando a credencial atinge a validade máxima, `ApplicationIdentityRegistry.resolve()` bloqueia seu uso. Não existe fallback automático para outra application mais privilegiada.

## Procedimento de rotação sem indisponibilidade

1. provisionar a nova credencial na mesma App Registration;
2. gravá-la no destino indicado por `next_secret_ref`;
3. validar autenticação usando o slot `next` em ambiente controlado;
4. promover a referência `next` para `current` no cofre/configuração governada;
5. atualizar `rotated_at`;
6. revogar a credencial anterior no provedor;
7. provisionar um novo slot `next` vazio/novo para o próximo ciclo;
8. registrar evidência da rotação sem armazenar o valor do segredo.

## Configuração

O arquivo de catálogo é indicado por:

```text
REQSYS_IDENTITY_GOVERNANCE_FILE=/caminho/identity-governance.json
```

Utilize `backend/config/identity-governance.example.json` apenas como contrato de exemplo. O arquivo real deve ser injetado pelo ambiente/deploy e não deve conter valores de segredo.

## Uso no código

```python
from app.core.identity_governance import ApplicationIdentityRegistry

registry = ApplicationIdentityRegistry.from_environment()
identity = registry.resolve(
    environment="production",
    purpose="teams-proactive-messaging",
    data_classification="confidential",
)
```

Após a resolução, `identity.client_id`, `identity.tenant_id` e a referência de segredo devem ser usados pelo adaptador responsável por obter o token. O segredo real continua sendo recuperado pelo cofre/provider configurado no ambiente.

## Evidências e auditoria

Não registrar tokens, client secrets ou conteúdo de credenciais em logs. A evidência mínima de rotação deve conter: nome do perfil, ambiente, finalidade, classificação, `client_id`, data da rotação, vencimento calculado, executor/correlation ID e resultado.
