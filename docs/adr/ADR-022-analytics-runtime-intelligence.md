# ADR-022 — Analytics Runtime Intelligence como capability transversal

## Status

Aceito em 2026-06-21.

## Contexto

O ReqSys/GovBI deve evoluir para uma plataforma enterprise de inteligência operacional auditável. A operação precisa consolidar analytics confiável, IA governada, runtime observável, validação automática, explainability, confiança mensurável, operação autônoma, governança contínua, arquitetura viva e qualidade operacional contínua.

A referência operacional consolidada é o checklist de validação de resultados estranhos:

1. comparar totais antes/depois;
2. validar extremos;
3. conferir médias;
4. testar filtros separadamente;
5. validar JOINs;
6. procurar nulos indevidos;
7. comparar com outra fonte;
8. revisar agregações;
9. analisar amostras manuais;
10. revisar regra de negócio aplicada.

## Decisão

Implementar **Analytics Runtime Intelligence (ARI)** como capability transversal oficial do ReqSys/GovBI.

## Escopo inicial implementado

- Endpoint backend `GET /v1/analytics-runtime-intelligence/snapshot`.
- Tela frontend `/analytics-runtime-intelligence` com retorno em tela.
- Menu lateral `ARI Center`.
- Modelo de score consolidado: health, confidence, AI governance e operational quality.
- Guard rails operacionais para bloqueio, falha e alerta.
- Retorno visual Figma/GitHub integrado ao painel.
- Teste automatizado de contrato do snapshot.
- Relatório HTML autocontido versionado.

## Consequências

### Positivas

- Centraliza a visão de confiança analítica.
- Expõe uma trilha operacional para IA governada e explainability.
- Permite evoluir validadores reais por adapter sem quebrar a UI.
- Cria uma base para Living Architecture e Operations Center.

### Riscos

- Scores iniciais são sintéticos e precisam ser conectados a evidências reais por fonte.
- O baseline de cardinalidade e thresholds estatísticos precisa ser versionado por domínio.
- Self-healing deve permanecer governado, com auditoria e autorização para ações críticas.

## Próximos incrementos

1. Conectar validadores reais de SQL Server/API/DW.
2. Persistir histórico de score por execução.
3. Adicionar drill-down por query, fonte, regra, requisito e incidente.
4. Integrar Figma/GitHub como artefato vivo de arquitetura e UI.
5. Promover gates ARI para CI/CD e runtime produtivo.
