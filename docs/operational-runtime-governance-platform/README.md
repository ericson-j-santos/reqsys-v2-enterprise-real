# Operational Runtime Governance Platform v1

## Objetivo

Consolidar os incrementos operacionais dos PRs #70, #74, #75 e #94 em uma plataforma única de governança operacional do ReqSys.

Esta frente substitui a evolução paralela e fragmentada por um trilho canônico de estabilização, observabilidade, operação autônoma governada e monitoramento de GitHub Actions.

## Fontes consolidadas

| PR | Camada | Papel na plataforma | Estado observado em 2026-06-22 |
|---|---|---|---|
| #70 | Pipeline Governance Layer | CI/CD determinístico, guardrails, regressão e observabilidade de pipelines | Aberto, draft, mergeable=false |
| #74 | Runtime Intelligence Layer | Telemetria, correlation_id, runtime intelligence, resiliência e diagnóstico | Aberto, draft, mergeable=false |
| #75 | Autonomous Operations Layer | Maturidade operacional, Runtime Health Validator e remediação governada | Aberto, mergeable=true |
| #94 | Operational Actions Center | Monitor operacional de GitHub Actions, classificação de runs e score de saúde | Aberto, draft, mergeable=true |

## Decisão operacional

Os quatro PRs deixam de ser tratados como frentes independentes. A partir desta consolidação, eles passam a compor a **Operational Runtime Governance Platform v1**.

## Arquitetura lógica

```text
Operational Runtime Governance Platform v1
├── Pipeline Governance Layer
│   ├── CI fast bloqueante
│   ├── security guardrails
│   ├── regression scheduled/manual
│   └── observabilidade de pipelines
├── Runtime Intelligence Layer
│   ├── correlation_id ponta a ponta
│   ├── runtime health
│   ├── diagnóstico operacional
│   └── score operacional explicável
├── Autonomous Operations Layer
│   ├── maturidade operacional
│   ├── health validator por componente
│   ├── executor governado de remediação
│   └── bloqueios de ações destrutivas
└── Operational Actions Center
    ├── monitoramento de GitHub Actions
    ├── classificação de workflow runs
    ├── score de saúde dos pipelines
    └── evidência para retry, correção e merge
```

## Matriz de consolidação

| Camada | Origem principal | Deve permanecer | Deve ser corrigido antes de 100% |
|---|---|---|---|
| Pipeline Governance | #70 | workflows enterprise, guardrails, runbook, ADR | atualizar contra main e corrigir falha de Backend Tests + Coverage |
| Runtime Intelligence | #74 | correlation_id, telemetry, runtime intelligence service, runbook | atualizar contra main e integrar router FastAPI |
| Autonomous Operations | #75 | maturity score, health validator, remediation executor, testes | validar CI real e alinhar nomenclatura P0.1/P0.2 |
| Actions Center | #94 | classificador de runs, score de saúde, API e documentação | validar CI real e integrar ao OCC |

## Critérios de aceite para declarar 100%

- [ ] PR #70 sem conflito, atualizado contra main e com CI fast verde.
- [ ] PR #74 sem conflito, atualizado contra main e com router backend integrado.
- [ ] PR #75 validado com testes de maturidade, health validator e remediação governada.
- [ ] PR #94 validado com testes do Actions Center.
- [ ] Endpoints operacionais documentados.
- [ ] Relatório HTML autocontido publicado.
- [ ] CI completo verde.
- [ ] Evidência real registrada no PR final.
- [ ] Squash merge autorizado somente após validação.

## Endpoints-alvo

| Área | Endpoint | Origem | Finalidade |
|---|---|---|---|
| Runtime | `GET /monitoramento-operacional/runtime/health` | #74 | Saúde operacional do runtime |
| Runtime | `GET /monitoramento-operacional/runtime/diagnostico` | #74 | Diagnóstico operacional explicável |
| AOP | `GET /operacao-autonoma/maturidade` | #75 | Maturidade operacional consolidada |
| AOP | `GET /operacao-autonoma/runtime-health` | #75 | Health validator por componente |
| AOP | `POST /operacao-autonoma/remediacoes/avaliar` | #75 | Avaliação governada de remediações |
| Actions | a documentar no PR #94 | #94 | Monitor de GitHub Actions e score de saúde |

## Ordem de execução

1. Usar esta branch como trilho canônico da consolidação.
2. Atualizar #70 e #74 contra main antes de qualquer merge.
3. Incorporar #75 e #94 somente após validação dos testes.
4. Consolidar documentação, endpoints e relatório HTML.
5. Executar CI fast.
6. Corrigir falhas sem relaxar gates.
7. Promover PR final para ready for review apenas com evidência.

## Governança

- Não declarar maturidade avançada sem evidência.
- Não remover gates para passar CI.
- Não mascarar falhas legadas.
- Não fundir PRs conflitantes diretamente.
- Manter rastreabilidade entre PR, ADR, runbook, release note e relatório HTML.

## Status atual

Estado: **em consolidação**.

Percentual evidenciado: **35%**.

Motivo: a documentação canônica foi criada e os insumos foram classificados, mas ainda existem PRs com `mergeable=false` e CI completo não evidenciado.
