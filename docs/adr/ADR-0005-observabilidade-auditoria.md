# ADR-0005 — Observabilidade, Auditoria e Correlação

Status: aceito
Data: 2026-06-20

## Contexto

A plataforma precisa permitir diagnóstico técnico, rastreabilidade de operações, análise de falhas e governança de uso sem expor informações sensíveis.

## Decisão

Toda operação relevante deve propagar um identificador de correlação e registrar eventos estruturados.

Padrões mínimos:

- Aceitar `X-Correlation-ID` ou gerar identificador quando ausente.
- Propagar o identificador entre frontend, API, serviços, jobs e integrações.
- Registrar eventos com severidade, origem, operação, ambiente e resultado.
- Mascarar informações sensíveis.
- Separar logs técnicos, métricas, auditoria e trilhas funcionais.

## Consequências

- Facilita análise de incidentes.
- Permite rastrear fluxo ponta a ponta.
- Reduz risco de vazamento em logs.

## Critérios de aceite

- Identificador de correlação presente nos fluxos críticos.
- Logs estruturados e sem conteúdo sensível.
- Falhas relevantes com mensagem rastreável.
- Métricas mínimas para disponibilidade, erro e latência.
