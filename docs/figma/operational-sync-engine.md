# Operational Sync Engine v1 — Retorno Visual

```mermaid
flowchart LR
  A["GitHub PRs e CI"] --> B["Operational Event Bus"]
  C["Google Calendar / Agenda"] --> B
  D["ReqSys Runtime Center"] --> B
  E["Figma / FigJam"] --> B
  B --> F["Operational Sync Engine v1"]
  F --> G["Score de Risco"]
  F --> H["Snapshot Auditavel"]
  F --> I["Relatorio HTML Autocontido"]
  F --> J["Proxima Acao Objetiva"]
  G --> K["Alertas Governados"]
  H --> K
  I --> K
  J --> K
```

## Critérios visuais obrigatórios

- Deve existir retorno navegável no repositório.
- Deve existir fallback `.html` autocontido.
- Deve existir diagrama versionado mesmo quando Figma/FigJam não estiver disponível.
- Deve existir referência explícita no PR.
