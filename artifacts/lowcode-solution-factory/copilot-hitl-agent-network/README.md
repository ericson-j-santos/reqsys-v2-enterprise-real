# ReqSys — Rede Corporativa de Agentes HITL

Blueprint materializável pela `LowCode Solution Factory` do ReqSys para Microsoft Copilot Studio, Power Automate e Dataverse.

## Objetivo

Implantar uma rede governada de agentes especializados, coordenada por um Supervisor, com estado persistente, aprovações multinível, retomada automática, auditoria, RBAC e integrações idempotentes.

## Componentes

- **Supervisor Agent:** mantém contexto canônico, seleciona especialistas e controla handoffs.
- **Agentes especializados:** Requisitos, BDD, QA, Governança e DevOps.
- **Dataverse:** instâncias, transições imutáveis, aprovações, execuções e outbox.
- **Power Automate:** intake, aprovações Analista → PO → Gestor, retomada, SLA e integrações.
- **Copilot Studio:** tópicos e actions que chamam flows; agentes não escrevem diretamente em sistemas externos.

## Ordem de materialização

1. Criar Solution não gerenciada em DEV com publisher `ReqSys` e prefixo `reqsys`.
2. Criar tabelas, choices, chaves alternativas e relacionamentos de `dataverse/schema.json`.
3. Habilitar auditoria do ambiente e das tabelas; restringir exclusão das tabelas append-only.
4. Criar connection references e environment variables descritas em `powerautomate/flows.json`.
5. Criar os sete cloud flows dentro da Solution.
6. Criar Supervisor e agentes especializados no Copilot Studio conforme `copilot/agents.json`.
7. Expor cada flow como action do Copilot Studio usando contratos JSON/OpenAPI versionados.
8. Configurar grupos Entra ID para Analista, PO, Gestor, Operação e Auditoria.
9. Exportar como managed solution para STG e PROD via pipeline ALM com aprovação humana.

## Matriz RBAC mínima

| Papel | Permissões |
| --- | --- |
| Solicitante | Criar solicitação e consultar itens próprios |
| Analista | Atualizar análise e decidir primeiro nível |
| Product Owner | Decidir valor, prioridade e escopo |
| Gestor | Autorizar risco residual e escrita externa |
| Operação | Reprocessar outbox e tratar dead-letter |
| Auditor | Leitura organizacional sem alteração |
| Service Principal | Executar flows com menor privilégio |

## Guardrails obrigatórios

- `correlation_id` em todas as tabelas, actions, logs e integrações.
- Concorrência otimista por `state_version`; rejeitar retomadas obsoletas.
- Histórico de transições e decisões somente append-only.
- Nenhum agente chama GitHub, Azure DevOps ou Redmine diretamente.
- Toda escrita externa nasce na outbox após cadeia de aprovação válida.
- Segredos apenas em connection references, environment variables secretas ou Azure Key Vault.
- DEV → STG → PROD com solution checker, testes, evidência e plano de rollback.

## Critérios de aceite

- Uma solicitação iniciada no Copilot Studio gera instância e `correlation_id` únicos.
- Handoffs preservam `workflow_instance_id` e `state_version`.
- Aprovação segue Analista → PO → Gestor com SLA, lembrete e escalonamento.
- Após decisão, o fluxo retoma automaticamente do estado persistido.
- Reexecução não duplica PR, work item, issue ou notificação.
- Auditor consegue reconstruir toda a linha do tempo sem depender de logs voláteis.
- Falha permanente é enviada para dead-letter e notifica Operação.

## Validação local do contrato

```bash
python -m pytest backend/tests/test_copilot_hitl_agent_network_blueprint.py -q
```

## Próximo incremento recomendado

Gerar automaticamente os artefatos importáveis da Solution (`solution.xml`, customizations e connection references) via PAC CLI, mantendo este blueprint como fonte canônica.
