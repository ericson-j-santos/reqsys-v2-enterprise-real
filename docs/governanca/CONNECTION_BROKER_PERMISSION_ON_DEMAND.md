# Connection Broker e Permission-on-Demand AI

## Objetivo

Padronizar como o ReqSys e seus agentes lidam com conectores externos, evitando que fluxos parem porque o usuário esqueceu de autorizar GitHub, Google, Microsoft, Figma, Dataverse ou outros provedores.

A solução não contorna OAuth nem elimina consentimento humano. Ela antecipa a validação, solicita permissão no momento correto e retoma o fluxo com segurança.

---

## Componentes

| Componente | Responsabilidade |
|---|---|
| Capability Registry | Catálogo de conectores, capabilities, escopos e ambientes. |
| Connection Health Check | Verificação de disponibilidade, token, escopo e expiração. |
| Permission Request Flow | Mensagem contextual para solicitar autorização ao usuário. |
| Resume Controller | Retomada segura da ação após autorização. |
| Audit Trail | Registro com `correlation_id`, ator, ambiente, capability e decisão. |
| Operational Dashboard | Exibição de status em `/monitoramento-operacional`. |

---

## Estados do conector

| Estado | Significado | Ação |
|---|---|---|
| `ready` | Autorizado e com escopo suficiente. | Executar. |
| `missing_permission` | Não autorizado. | Solicitar permissão contextual. |
| `insufficient_scope` | Autorizado, mas sem escopo suficiente. | Solicitar novo consentimento com escopo mínimo. |
| `expired` | Token expirado. | Tentar refresh seguro; se falhar, solicitar reconexão. |
| `unavailable` | Conector indisponível. | Bloquear ação e registrar incidente. |
| `misconfigured` | Configuração incompleta. | Bloquear em produção e abrir pendência técnica. |

---

## Contrato recomendado

```json
{
  "id": "github.pr.write",
  "connector": "github",
  "description": "Criar branch, commit e pull request",
  "environments": ["dev", "homolog", "prod"],
  "minimum_scopes": ["contents:write", "pull_requests:write"],
  "criticality": "high",
  "requires_human_confirmation": true,
  "fallback": "Gerar patch/documentação manual quando autorização não existir"
}
```

---

## Fluxo operacional padrão

1. Usuário solicita uma ação.
2. Agente resolve a capability necessária.
3. Broker valida autorização e escopos.
4. Se `ready`, executa.
5. Se não autorizado, solicita permissão contextual.
6. Após consentimento, revalida.
7. Se válido, retoma execução.
8. Registra auditoria.
9. Atualiza painel operacional.

---

## Mensagens padrão para o chat

### Falta de permissão

```text
Para continuar, preciso acessar o conector GitHub com permissão mínima para criar branch, commit e pull request. Autorize o conector e eu retomo esta execução mantendo o contexto.
```

### Escopo insuficiente

```text
O conector GitHub está conectado, mas não possui escopo suficiente para escrita no repositório. Autorize o escopo mínimo necessário para continuar.
```

### Token expirado

```text
A autorização do conector expirou. Reconecte o conector para que eu possa retomar a execução com segurança.
```

---

## Segurança e governança

- Não registrar tokens, refresh tokens, secrets ou connection strings.
- Não serializar credenciais em HTML estático.
- Não solicitar escopos amplos sem justificativa.
- Não executar escrita em produção sem gate e confirmação aplicável.
- Registrar `correlation_id` em toda verificação.
- Segregar configurações por ambiente.
- Manter revisão humana para ações sensíveis.

---

## Testes mínimos

| Tipo | Cenário |
|---|---|
| Unitário | Resolução de capability por ação. |
| Unitário | Classificação de status: ready, expired, missing_permission. |
| Contrato | Schema do registry. |
| Integração | Health-check por conector. |
| E2E | Solicitar permissão, autorizar e retomar ação. |
| Segurança | Garantir ausência de token/secret em logs. |
| Produção | Bloquear deploy se capability crítica estiver sem configuração. |

---

## Integração com `/monitoramento-operacional`

Adicionar cards de conectores críticos indisponíveis, tokens próximos de expirar, capabilities sem escopo mapeado, falhas de autorização por ambiente, última autorização por conector e ações bloqueadas por gate.

---

## Decisão final

O ReqSys deve tratar conectores como dependências críticas de runtime, não como configuração manual isolada. O padrão oficial passa a ser: validar, solicitar permissão contextual, retomar execução e auditar.
