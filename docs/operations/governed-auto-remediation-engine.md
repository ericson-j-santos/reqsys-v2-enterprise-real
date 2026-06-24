# Governed Auto Remediation Engine

## Objetivo

Adicionar camada governada de remediação operacional para incidentes de CI/CD.

## Capacidades implementadas

- Classificação de severidade.
- Política de rerun governada.
- Controle de retry storms.
- Regras de aprovação manual.
- Trilha de auditoria.
- Recomendações operacionais.
- Artifact reutilizável.

## Severidades

- LOW
- MEDIUM
- HIGH

## Políticas de rerun

- NO_ACTION
- LIMITED_RERUN
- MANUAL_APPROVAL_REQUIRED

## Benefícios

- Menos reruns descontrolados.
- Menor risco operacional.
- Melhor governança CI/CD.
- Melhor auditabilidade.
- Base para operação semi-autônoma.

## Próximos incrementos previstos

- Execução automática limitada.
- Controle temporal de reruns.
- Analytics históricos de remediação.
- Correlação incidente ↔ deploy.
- Auto-remediação inteligente supervisionada.
