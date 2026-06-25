# ReqSys Agile Runtime Core

**Status:** P0 — núcleo arquitetural e contrato operacional  
**Data:** 2026-06-25  
**Repositório de aplicação:** `reqsys-v2-enterprise-real`  
**Decisão:** implementar como módulo interno do ReqSys Enterprise, não como novo repositório isolado.

## 1. Decisão arquitetural

O Agile Runtime Core deve ser incorporado ao `reqsys-v2-enterprise-real` porque o repositório já concentra o produto enterprise com cadastro, backlog, histórias, rastreabilidade, auditoria, integrações corporativas, backend, frontend, Docker e matriz de ambientes.

Criar um repositório separado neste momento aumentaria acoplamento distribuído, duplicidade de contratos, sincronização entre domínios e risco de divergência entre requisito, backlog, sprint, PR/MR, CI e deploy.

## 2. Contexto

O ReqSys evolui de uma plataforma de engenharia de requisitos para um runtime operacional de entrega:

```text
Requisito → Backlog → Sprint → Execução → PR/MR → CI/CD → Deploy → Evidência → Monitoramento
```

O Agile Runtime Core não deve ser um clone de Jira. Ele deve atuar como camada de orquestração ágil, rastreabilidade e analytics sobre o fluxo já existente do ReqSys.

## 3. Escopo P0

| Capacidade | Estado neste incremento | Observação |
|---|---:|---|
| Sprint model | Contrato definido | Base para planejamento, capacidade e métricas |
| Backlog model | Contrato definido | Epic, Feature, Story, Task, Bug, Spike, Risk, TechDebt e ADR |
| Workflow states | Contrato definido | Estados governados de entrega |
| Kanban operacional | Definido | Derivado do workflow, não CRUD isolado |
| Sprint analytics | Definido | Velocity, lead time, cycle time, throughput, burndown e CI pass rate |
| IA routing | Definido | Direcionamento para agente/IA responsável |
| GitHub/GitLab linking | Definido | PR/MR, branch, pipeline e evidência |
| CI evidence mapping | Definido | Workflow/pipeline, status, URL, artefato e ambiente |
| Story → PR → CI → Deploy | Definido | Rastreabilidade ponta a ponta |

## 4. Fronteira correta do módulo

### Dentro do ReqSys Enterprise

Deve ficar no mesmo repositório:

- modelo de domínio ágil;
- APIs de backlog/sprint/workflow;
- componentes de UI Kanban/Sprint;
- analytics operacionais;
- rastreabilidade com requisitos;
- integração com auditoria;
- integração com qualidade IA;
- mapeamento com PR/MR, CI/CD e deploy.

### Fora do núcleo, via adaptadores

Devem permanecer desacoplados por portas/adaptadores:

- GitHub;
- GitLab;
- Redmine/Jira/Azure DevOps, se usados;
- provedores de CI/CD;
- provedores de e-mail;
- provedores de Teams/Forms;
- webhooks externos.

## 5. Risco de arquitetura excessiva

O risco existe se o módulo for implementado com microserviços ou repositório separado antes de haver demanda real de escala independente.

A decisão recomendada é:

```text
monólito modular enterprise agora
→ extração futura somente se houver escala, ownership ou ciclo de release independente
```

## 6. Critérios para extrair para novo repositório no futuro

Criar um repositório separado só será recomendado se pelo menos 3 critérios forem verdadeiros:

1. O Agile Runtime for consumido por mais de um produto além do ReqSys.
2. O ciclo de release precisar ser independente do ReqSys.
3. Houver time/owner separado para o módulo.
4. O volume de integrações externas exigir SDK/serviço próprio.
5. O módulo precisar escalar ou ser implantado isoladamente.
6. O contrato público virar produto independente.

Enquanto isso não ocorrer, novo repositório é custo operacional desnecessário.

## 7. Modelo operacional alvo

```text
ReqSys Enterprise
├── Requirements Core
├── Agile Runtime Core
│   ├── Backlog
│   ├── Sprint
│   ├── Workflow
│   ├── Kanban
│   ├── Analytics
│   ├── AI Routing
│   └── Evidence Mapping
├── Integrations
│   ├── GitHub Adapter
│   ├── GitLab Adapter
│   ├── CI/CD Adapter
│   └── Notification Adapter
└── Audit / Observability / Governance
```

## 8. Métricas iniciais

| Dimensão | Atual estimado | Alvo após implementação funcional |
|---|---:|---:|
| Agile Runtime | 22% | 85% |
| Rastreabilidade Story → Deploy | 35% | 90% |
| Analytics de sprint | 20% | 85% |
| Automação de roteamento IA | 40% | 80% |
| Governança ágil | 45% | 90% |

## 9. Próximo incremento recomendado

Implementar a primeira fatia funcional vertical:

```text
Story + Sprint + Workflow State + Evidence Link
```

Com isso, o ReqSys passa a registrar uma história, vinculá-la a uma sprint, mover estado de workflow e anexar evidência de PR/MR e CI/CD.

## 10. Restrições

- Não criar outro repositório neste momento.
- Não introduzir microserviço sem necessidade comprovada.
- Não duplicar backlog externo como fonte da verdade.
- Não declarar maturidade avançada sem implementação funcional, teste e evidência.
- Não acoplar diretamente GitHub/GitLab no domínio; usar portas/adaptadores.
