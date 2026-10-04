# Analytics Runtime Intelligence e Operational Sync

## Objetivo

Fornecer síntese analítica auditável sem confundir contrato local, sample ou fallback com evidência operacional real.

## Requisitos

1. O frontend deve consumir a rota canônica sob `/api` compatível com o proxy Vite.
2. O alias `/v1` pode permanecer por compatibilidade.
3. Sem staging externo completo, `production_ready` deve ser falso.
4. Adapter SQL não executa consultas e não constitui evidência produtiva.
5. Staging validator não pode possuir defaults positivos.
6. Telemetria/lineage de contrato não podem ser promovidos a evidência real.
7. Figma sem readback atual deve permanecer `evidence_pending`.
8. Fallback do frontend é sempre fail-closed.
9. Operational Sync recebe evidência explícita; sem input retorna `evidence_required`.
10. Estados de PR/CI não podem ser hardcoded como se fossem atuais.
11. ARI deve estar integrado a router, navegação responsiva e responsabilidade ReqSys 360.
12. `/monitoramento-operacional` continua sendo a fonte canônica do estado técnico corrente.
13. Nenhum deploy ou promoção de ambiente faz parte deste incremento.

## Critérios de aceite

- testes backend/frontend/engine verdes;
- SDD, ReqSys 360, segurança e governança verdes;
- `behind_by=0`;
- PR sem conflitos e mergeável;
- nenhum falso positivo de production readiness.
