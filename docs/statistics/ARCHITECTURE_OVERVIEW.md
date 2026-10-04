# Overview Arquitetural — Aba Estatísticas v1

```mermaid
flowchart LR
  Menu[Menu Principal] --> Rota[/estatisticas]
  Rota --> View[EstatisticasView.vue]
  View --> Service[estatisticas.js]
  Service --> Internas[Indicadores internos iniciais]
  Service --> Externas[Registry externo nao_medido]
  Service --> GuardRails[validarIndicador]
  View --> Cards[Cards executivos]
  View --> Filtros[Filtros]
  View --> Analitico[Tabela analítica]
```

## Decisão

A v1 fica no frontend com contrato estável e guard rails. A v2 deve preservar esse contrato e trocar a origem local por API backend real.

## Fronteiras

| Camada | Responsabilidade |
|---|---|
| Router | Expor `/estatisticas` |
| Layout | Expor menu principal |
| View | Apresentar dados, filtros e analítico |
| Service | Contrato, dados iniciais, resumo e validações |
| Testes | Validar guard rails mínimos |
