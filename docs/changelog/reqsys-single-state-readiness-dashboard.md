# ReqSys Single State Readiness Dashboard

## Objetivo

Publicar um painel HTML autocontido e auditável para a readiness dos consumidores do Estado Único ReqSys.

## Escopo

- Governança, Runtime e Analytics em um único indicador;
- leitura exclusiva do contrato `reqsys-single-state-consumer-readiness`;
- operação offline, determinística e report-only;
- sem chamadas externas, promoção automática ou bloqueio de produção.

## Evidências

O workflow publica no mesmo artifact, retido por 90 dias:

- `report.json`, contrato estruturado de readiness;
- `index.html`, painel executivo autocontido.

## Segurança

Todo conteúdo do contrato é escapado antes da renderização HTML. O painel não executa JavaScript e não recebe segredos ou dados pessoais.
