# Exemplo — Arquitetura Viva do Ciclo ReqSys

## Objetivo

Demonstrar como um fluxo vivo deve representar requisitos, código, runtime, analytics e governança.

## Fluxo Macro

```mermaid
flowchart LR
    REQ[Requisito] --> IA[Analise por IA]
    IA --> BKL[Backlog]
    BKL --> BR[Branch]
    BR --> PR[Pull Request Draft]
    PR --> CI[CI/CD]
    CI --> HOM[Homologacao]
    HOM --> PROD[Producao]
    PROD --> OBS[Observabilidade]
    OBS --> ANA[Analytics]
    ANA --> IMP[Analise de Impacto]
```

## Metadados Esperados

```json
{
  "id": "diag-reqsys-ciclo-001",
  "title": "Ciclo Vivo ReqSys",
  "version": "1.0.0",
  "environment": "dev",
  "sources": [
    {
      "id": "src-adr-arch-001",
      "type": "adr",
      "name": "ADR-ARCH-001 — Arquitetura Viva"
    },
    {
      "id": "src-code-platform-architecture",
      "type": "codigo",
      "name": "src/platform/architecture-visualization"
    }
  ],
  "audit": {
    "generatedAt": "2026-06-20T00:00:00-03:00",
    "generatedBy": "architecture-visualization-engine",
    "hash": "sha256:exemplo",
    "confidence": "alta"
  }
}
```

## Interpretação

Este exemplo representa o caminho mínimo esperado para rastrear uma demanda desde a origem funcional até o monitoramento em produção.

A visão final deve permitir drill-down em cada nó:

- requisito;
- critério de aceite;
- branch;
- PR;
- workflow CI/CD;
- ambiente;
- logs;
- traces;
- dashboards;
- impactos.

## Critério de Aceite

- O diagrama possui fonte rastreável.
- O ambiente está identificado.
- Existe versão.
- Existe trilha de auditoria.
- A explicação por IA não inventa dependências sem fonte.
- O conteúdo não expõe PII, secrets ou credenciais.
