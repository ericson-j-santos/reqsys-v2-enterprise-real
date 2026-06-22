# API — Monitoramento Operacional

## Endpoint

`GET /monitoramento-operacional`

No frontend Vite, a chamada deve usar `/api/monitoramento-operacional`, permitindo que o proxy remova o prefixo `/api` e encaminhe para o backend.

## Objetivo

Retornar um snapshot operacional do ReqSys com envelope padrão, estado geral, itens monitorados, correlação, próximos passos, critérios de fechamento e métricas estimadas de tempo operacional.

## Versão do contrato

`schema_version = 1.2.0`

A versão `1.2.0` adiciona o bloco `tempo_operacional` ao contrato `1.1.0`, mantendo rastreabilidade operacional para frentes estratégicas ainda abertas sem declará-las resolvidas sem implementação real e CI verde.

## Campos principais

- `schema_version`
- `correlation_id`
- `coletado_em`
- `ambiente`
- `resumo`
- `tempo_operacional`
- `itens`

## Resumo

- `estado_geral`
- `bloqueios`
- `pendencias`
- `total_itens`
- `frentes_criticas`
- `itens_prontos_para_merge`

## Tempo operacional

- `previsao_proxima_acao`
- `eta_proxima_verificacao_minutos`
- `tempo_medio_proxima_acao_minutos`
- `tempo_medio_resolucao_horas`
- `tempo_medio_review_minutos`
- `sla_operacional_minutos`

## Item monitorado

- `tipo`
- `referencia`
- `titulo`
- `estado`
- `severidade`
- `origem`
- `pronto_para_merge`
- `bloqueante`
- `proximo_passo`
- `criterio_de_fechamento`
- `detalhes`

## Estados

- `verde`
- `amarelo`
- `vermelho`
- `bloqueado`
- `desconhecido`

## Regras

1. `bloqueado` prevalece sobre demais estados.
2. Lista vazia retorna `desconhecido`.
3. CI verde é condição necessária, mas não suficiente.
4. O frontend não consulta serviços externos diretamente.
5. O snapshot é interno e não expõe secrets, payloads sensíveis ou dados pessoais.
6. Pendência estratégica só pode mudar para `verde` com implementação, teste e CI validado.
7. Métricas de tempo operacional são estimativas operacionais; não substituem evidência real de CI, revisão ou runtime.

## Itens cobertos

| Referência | Tema | Estado operacional |
| --- | --- | --- |
| REQSYS-OPER-001 | GovBI IA com grounding e falha controlada | vermelho/bloqueante |
| REQSYS-OPER-002 | Dashboard para Analítico filtrado | amarelo |
| REQSYS-OPER-003 | Planner via Low Code e API | amarelo |
| REQSYS-OPER-004 | Pipeline operacional e CI/CD | amarelo |
| REQSYS-OPER-005 | Monitoramento operacional publicado | verde |
| production-gates | Gates obrigatórios | verde |

## Evidências esperadas no PR

- `backend/tests/test_monitoramento_operacional.py` cobrindo endpoint, correlação, frentes prioritárias, próximos passos, critérios de fechamento, tempo operacional e precedência de bloqueio.
- CI verde no último head antes de qualquer mudança de draft para pronto.
- Artifact de evidência publicado quando aplicável.
- Comentário de PR com evidência dos jobs executados.

Refs #30 #31 #32 #33 #46
