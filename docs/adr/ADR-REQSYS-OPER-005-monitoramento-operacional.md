# ADR — REQSYS-OPER-005 — Monitoramento Operacional

## Status

Proposto.

## Contexto

O ReqSys precisa exibir sinais mínimos de operação, validação e governança em uma área própria.

## Decisão

Criar endpoint backend `/monitoramento-operacional` e tela frontend correspondente, com snapshot inicial interno e evolução posterior para coletores reais.

## Consequências

- Centraliza a visão operacional.
- Cria base para analytics e drill-down.
- Evita consultas externas diretamente pelo navegador.
- Mantém merge e deploy fora do escopo automático.

Refs #46
