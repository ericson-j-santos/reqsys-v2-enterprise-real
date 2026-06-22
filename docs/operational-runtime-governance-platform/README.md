# Operational Runtime Governance Platform v1

## Objetivo

Consolidar os incrementos operacionais dos PRs #70, #74, #75 e #94 em uma plataforma única de governança operacional do ReqSys.

Esta frente substitui a evolução paralela e fragmentada por um trilho canônico de estabilização, observabilidade, operação autônoma governada e monitoramento de GitHub Actions.

## Fontes consolidadas

| PR | Camada | Papel na plataforma | Estado observado em 2026-06-22 |
|---|---|---|---|
| #70 | Pipeline Governance Layer | CI/CD determinístico, guardrails, regressão e observabilidade de pipelines | Divergente; extração parcial aplicada no #97 |
| #74 | Runtime Intelligence Layer | Telemetria, correlation_id, runtime intelligence, resiliência e diagnóstico | Divergente; core extraído sem tocar no bootstrap |
| #75 | Autonomous Operations Layer | Maturidade operacional, Runtime Health Validator e remediação governada | Preservado como núcleo operacional principal |
| #94 | Operational Actions Center | Monitor operacional de GitHub Actions, classificação de runs e score de saúde | Integração adiada até CI estabilizado |

## Decisão operacional

Os quatro PRs deixam de ser tratados como frentes independentes. A partir desta consolidação, eles passam a compor a **Operational Runtime Governance Platform v1**.

## Extração aplicada no PR #97

### Extraído do PR #70

| Arquivo | Finalidade |
|---|---|
| `.github/workflows/ci-enterprise-fast.yml` | CI fast bloqueante, com guardrails, backend fast e frontend fast |
| `.github/workflows/ci-enterprise-regression.yml` | Regressão agendada/manual, E2E, backend regression e artifacts |
| `scripts/ci_enterprise_guardrails.py` | Guardrails determinísticos de CI, segurança, lockfiles e relatórios |

### Extraído do PR #74

| Arquivo | Finalidade |
|---|---|
| `backend/app/core/correlation.py` | `correlation_id` ponta a ponta |
| `backend/app/core/telemetry.py` | logging operacional estruturado e medição de operações |
| `backend/app/models/operational_intelligence_models.py` | modelos Pydantic de runtime intelligence |
| `backend/app/services/runtime_intelligence_service.py` | score operacional determinístico e explicável |
| `backend/app/services/autonomous_operation_service.py` | recomendador seguro de ações operacionais |
| `backend/app/api/operational_intelligence.py` | endpoints runtime health e diagnóstico |

## Itens explicitamente não aplicados neste ciclo

| Item | Motivo |
|---|---|
| Alteração em `backend/app/main.py` | Evitar conflito no bootstrap FastAPI antes de validar estrutura atual da `main` |
| Frontend Runtime Center do #74 | Evitar conflito de rotas/layout antes do CI estabilizado |
| Actions Center do #94 | Deve entrar depois do CI fast validar a extração inicial |
| Merge bruto de #70/#74 | Branches divergentes demais contra `main` |

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

| Camada | Origem principal | Status no #97 | Deve ser corrigido antes de 100% |
|---|---|---|---|
| Pipeline Governance | #70 | Extração inicial aplicada | validar CI fast, corrigir achados sem relaxar gates |
| Runtime Intelligence | #74 | Core extraído | integrar router FastAPI após inspeção do bootstrap atual |
| Autonomous Operations | #75 | Preservado como núcleo principal | validar CI real e alinhar nomenclatura P0.1/P0.2 |
| Actions Center | #94 | Aguardando CI estabilizado | integrar ao OCC depois do fast path verde |

## Critérios de aceite para declarar 100%

- [x] Guardrails/workflows estáveis do #70 extraídos para o #97.
- [x] Runtime intelligence core do #74 extraído para o #97.
- [x] AOP do #75 preservado como núcleo operacional principal.
- [ ] PR #94 integrado depois do CI estabilizado.
- [ ] Router backend integrado no bootstrap FastAPI.
- [x] Endpoints operacionais documentados.
- [x] Relatório HTML autocontido publicado.
- [ ] CI fast verde.
- [ ] CI completo verde.
- [ ] Evidência real registrada no PR final.
- [ ] Squash merge autorizado somente após validação.

## Endpoints-alvo

| Área | Endpoint | Origem | Finalidade |
|---|---|---|---|
| Runtime | `GET /monitoramento-operacional/runtime/health` | #74 | Saúde operacional do runtime |
| Runtime | `POST /monitoramento-operacional/runtime/diagnostico` | #74 | Diagnóstico operacional explicável |
| AOP | `GET /operacao-autonoma/maturidade` | #75 | Maturidade operacional consolidada |
| AOP | `GET /operacao-autonoma/runtime-health` | #75 | Health validator por componente |
| AOP | `POST /operacao-autonoma/remediacoes/avaliar` | #75 | Avaliação governada de remediações |
| Actions | a integrar depois do CI fast | #94 | Monitor de GitHub Actions e score de saúde |

## Ordem de execução remanescente

1. Aguardar execução do CI fast no #97.
2. Corrigir falhas do guardrail sem relaxar gates.
3. Inspecionar `backend/app/main.py` atual e integrar `operational_intelligence.router` com menor mudança segura.
4. Integrar Actions Center do #94 ao OCC.
5. Validar CI completo.
6. Promover PR final para ready for review apenas com evidência.

## Governança

- Não declarar maturidade avançada sem evidência.
- Não remover gates para passar CI.
- Não mascarar falhas legadas.
- Não fundir PRs conflitantes diretamente.
- Manter rastreabilidade entre PR, ADR, runbook, release note e relatório HTML.

## Status atual

Estado: **extração inicial implementada**.

Percentual evidenciado: **55%**.

Motivo: a documentação canônica, HTML, workflows/guardrails do #70 e runtime intelligence core do #74 foram aplicados no #97. Ainda faltam CI fast verde, integração segura no bootstrap e Actions Center.
