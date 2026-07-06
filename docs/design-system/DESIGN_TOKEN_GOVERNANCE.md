# Governança de Design Tokens

## Objetivo

Centralizar tokens visuais do ReqSys em um contrato único reutilizável por:

- Vuetify
- CSS global
- Dashboards
- PDFs
- Exportações
- Figma
- Automação visual
- Visual regression

## Arquivo canônico

```text
frontend/src/theme/design-tokens.json
```

## Benefícios

- Evita hardcode de cores.
- Permite visual regression governada.
- Facilita integração futura com Figma.
- Reduz divergência entre frontend, analytics e exports.
- Permite versionamento semântico do design system.

## Próximo incremento recomendado

Adicionar pipeline de visual regression com:

- Playwright screenshot baseline.
- Snapshot governado.
- Diff percentual.
- Gate de regressão visual.
- Artifact de evidência.
