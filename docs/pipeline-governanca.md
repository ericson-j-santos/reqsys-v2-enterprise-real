# Governanca do pipeline ReqSys

Este documento consolida a frente REQSYS-OPER-004.

## Estado levantado

- CI principal: `.github/workflows/ci.yml`.
- Validacao publica: `.github/workflows/validacao-acessos.yml`.
- Issues abertas relacionadas: #30, #31, #32 e #33.
- PRs abertos observados nesta rodada: #44, #43, #25, #35, #34 e #23.
- Ultima evidencia verde antes do incremento complementar: `CI — ReqSys v2 Enterprise`, run #131, commit `f066d19a4c2960d87ce7739047cbf150e1ec1395`.

## Decisao operacional

A frente prioritaria continua sendo #33, pois ela sustenta GovBI IA, Dashboard Analitico e Planner com validacao bloqueante e evidencia rastreavel.

## Contrato minimo de evidencia

O script `scripts/validar-pipeline-governanca.mjs` emite um JSON canonico com os seguintes campos:

- `schemaVersion`;
- `generatedAt`;
- `correlationId`;
- `repository`;
- `issue`;
- `environment`;
- `run`;
- `status`;
- `estadoGeral`;
- `bloqueios`;
- `pendencias`;
- `itensMonitorados`.

Cada item monitorado deve conter identificador, tipo, referencia, titulo, obrigatoriedade, expectativa, resultado, estado, severidade e origem.

## Estados operacionais

| Estado | Uso |
|---|---|
| `verde` | Gate ou evidencia concluida com sucesso. |
| `amarelo` | Gate ignorado ou pendencia nao bloqueante. |
| `bloqueado` | Falha tecnica, cancelamento ou acao obrigatoria pendente. |
| `desconhecido` | Sinal nao informado ou indisponivel. |

## Comando versionado

```bash
npm run validate:pipeline
```

O comando gera o relatorio em stdout. Em CI, ele deve receber os resultados dos jobs obrigatorios por variaveis de ambiente e publicar o JSON como artifact `pipeline-governanca-report`.

## Criterio de pronto

Nenhum PR deve ser considerado pronto sem CI verde e evidencia publicada no proprio workflow.

## Proximo incremento executavel

Plugar o contrato `pipeline-governanca-report` ao workflow principal sem alterar os gates existentes de backend, frontend, responsividade e validacao publica. A etapa deve publicar artifact mesmo em falha e bloquear merge quando `estadoGeral` for diferente de `verde`.
