# Operational Intelligence Platform

## Objetivo

Consolidar o PR #74 sobre a arquitetura atual do ReqSys, preservando as capacidades já integradas e removendo divergência histórica sem criar segunda implementação de runtime, resiliência, persistência ou UI.

## Requisitos

1. Os endpoints de health e diagnóstico originados no #74 permanecem executáveis.
2. O router de operational intelligence permanece incluído no bootstrap FastAPI.
3. O diagnóstico deve ser determinístico, explicável e limitado a score de 0 a 100.
4. Operação autônoma assistida deve exigir aprovação em estados degradado/bloqueado.
5. Correlação e telemetria devem usar as superfícies canônicas atuais.
6. A UI operacional deve permanecer unificada em `MonitoramentoOperacionalView.vue`.
7. O serviço histórico `resilience_service.py` não deve ser reaplicado como executor paralelo; retry/remediação seguem a governança atual.
8. O DDL histórico `backend/sql/002_operational_intelligence_platform.sql` não deve ser aplicado diretamente; persistência deve usar estratégia atual de modelos/migrações.
9. O workflow histórico `operational-intelligence-governance.yml` não deve duplicar os gates canônicos.
10. Nenhum deploy, promoção, segredo ou alteração administrativa faz parte da reconciliação.

## Critérios de aceite

- contrato preventivo e testes críticos do backend verdes;
- SDD, segurança e governança verdes;
- `behind_by=0`;
- PR sem conflitos e mergeável;
- nenhum artefato histórico incompatível reintroduzido.
