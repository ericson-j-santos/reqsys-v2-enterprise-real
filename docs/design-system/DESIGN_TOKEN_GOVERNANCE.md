# Governança de Design Tokens

## Objetivo

Centralizar os tokens visuais do ReqSys em um contrato único, versionável e reutilizável por múltiplas superfícies.

## Arquivo canônico

```text
frontend/src/theme/design-tokens.json
```

## Superfícies previstas

- Vuetify
- CSS global
- Dashboards
- PDFs
- Exportações
- Figma
- Automação visual
- Visual regression

## Benefícios

- Evita hardcode de cores em componentes.
- Reduz divergência entre frontend, analytics e exports.
- Facilita integração futura com Figma.
- Permite versionamento semântico do design system.
- Cria base para validação automatizada de regressão visual.

## Mapeamento semântico

| Conceito | Token semântico | Token base |
| --- | --- | --- |
| Governança | `governance` | `primary` |
| Destaque executivo | `executiveHighlight` | `accent` |
| Informação/analytics | `informational` | `analytics` |
| Saudável | `healthy` | `success` |
| Atenção/degradado | `degraded` | `warning` |
| Crítico | `criticalState` | `critical` |

## Fora de escopo deste incremento

- Substituir todos os usos diretos de cor nos componentes.
- Alterar runtime, API, backend, banco ou deploy.
- Adicionar gate bloqueante de visual regression.

## Próximo incremento recomendado

Adicionar pipeline governado de visual regression com:

- Playwright screenshot baseline.
- Snapshot versionado.
- Diff percentual.
- Artifact visual no CI.
- Aprovação humana para mudanças visuais intencionais.
