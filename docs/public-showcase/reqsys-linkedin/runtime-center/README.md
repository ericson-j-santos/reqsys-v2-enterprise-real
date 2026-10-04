# ReqSys Runtime Operational Center P0 — showcase estático

## Objetivo

Preservar o corte visual criado no PR #76 como material demonstrativo do conceito de Runtime Center.

> Este diretório é um **showcase estático**. Os estados, métricas, horários e serviços exibidos não são evidência do runtime atual e não devem ser usados para autorizar merge, deploy ou promoção de ambiente.

## Entregas

- página renderizável em `index.html`;
- estilos responsivos em `runtime-center.css`;
- contrato ilustrativo em `runtime-health.contract.json`;
- contrato preventivo em `tests/test_runtime_center_p0_showcase.py`.

## Fonte operacional real

A situação operacional real do ReqSys deve ser obtida das superfícies canônicas atuais, incluindo:

- `/api/runtime/health`;
- `/api/runtime/readiness`;
- `/api/runtime/metrics`;
- `/api/runtime/dashboard`;
- `/monitoramento-operacional/runtime/health`;
- `/monitoramento-operacional/runtime/diagnostico`.

## Critério de estabilização do showcase

1. a página abre como documento estático;
2. health, timeline, indicadores, arquitetura e incidentes são visíveis;
3. existe aviso explícito de conteúdo ilustrativo;
4. o contrato JSON declara modo `illustrative` e `operational_evidence=false`;
5. o CI atual permanece verde no HEAD do PR.

## Governança

Self-healing, merge, deploy e estado de saúde real não podem ser inferidos deste material estático.
