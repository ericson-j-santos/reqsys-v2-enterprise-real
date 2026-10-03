# Changelog — Estatísticas ReqSys

## 2026-06-21 — Incremento planejado

### Adicionado

- Especificação da aba `Estatísticas`.
- Separação entre estatísticas internas evidenciadas e estatísticas externas auditáveis.
- Modelo mínimo de indicadores estatísticos.
- Guard rails para fontes, fórmulas, mocks, TTL e promoção indevida de estado.
- Critérios de aceite para UI, analítico, governança e publicação.
- ADR arquitetural vinculada: `docs/adr/ADR-ESTATISTICAS-INTERNAS-EXTERNAS.md`.

### Decisão

A aba deve evoluir primeiro com dados internos e contrato definitivo. Dados externos entram somente com origem, data de coleta, TTL, confiabilidade e rastreabilidade.

### Pendente

- Implementar rota/menu `/estatisticas`.
- Criar componentes visuais.
- Criar contrato TypeScript no código da aplicação.
- Adicionar testes unitários, responsivos e de guard rails.
- Conectar GitHub Actions, PRs, requisitos e fontes externas.
