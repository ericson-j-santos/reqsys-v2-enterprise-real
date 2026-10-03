# Release Note — Monitoramento Operacional ReqSys

Data: 2026-06-20
Frente: REQSYS-OPER-004
Tipo: documentação / arquitetura / observabilidade

## Resumo

Adicionada especificação inicial para criação do módulo mínimo de Monitoramento Operacional do ReqSys.

## Motivação

O acompanhamento atual de PRs, CI, gates, validação pública e pendências críticas depende de consultas externas e agendamentos. O ReqSys deve evoluir para exibir esses sinais internamente, com rastreabilidade, filtros analíticos e visão executiva.

## Escopo documentado

- Fontes mínimas de sinal operacional.
- Estados canônicos de monitoramento.
- Regras para PR em draft, CI verde e gates críticos.
- UI mínima com cards e analítico filtrável.
- Testes mínimos esperados.
- Definition of Done para futura implementação.

## Impacto

Não altera comportamento de produção. Esta entrega prepara a base documental para implementação posterior do painel e dos contratos de monitoramento.

## Próximo incremento recomendado

Criar contrato versionado de API ou mock para `/monitoramento-operacional`, com testes de contrato e classificador de estado.

Refs: #33
