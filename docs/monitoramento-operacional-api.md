# API — Monitoramento Operacional

## Endpoint

`GET /monitoramento-operacional`

No frontend Vite, a chamada deve usar `/api/monitoramento-operacional`, permitindo que o proxy remova o prefixo `/api` e encaminhe para o backend.

## Objetivo

Retornar um snapshot operacional mínimo do ReqSys com envelope padrão, estado geral, itens monitorados e correlação.

## Campos principais

- `schema_version`
- `correlation_id`
- `coletado_em`
- `ambiente`
- `resumo`
- `itens`

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
5. O snapshot inicial é interno e não expõe secrets, payloads sensíveis ou dados pessoais.

## Itens cobertos na primeira fatia

| Referência | Tema | Estado inicial |
| --- | --- | --- |
| REQSYS-OPER-001 | GovBI IA | vermelho |
| REQSYS-OPER-002 | Dashboard para Analítico filtrado | amarelo |
| REQSYS-OPER-003 | Planner via Low Code e API | amarelo |
| REQSYS-OPER-004 | Pipeline operacional e CI | amarelo |
| REQSYS-OPER-005 | Monitoramento operacional | amarelo |
| production-gates | Gates obrigatórios | verde |

## Evidências esperadas no PR

- `backend/tests/test_monitoramento_operacional.py` cobrindo endpoint, correlação, frentes prioritárias e precedência de estado.
- `frontend/src/views/MonitoramentoOperacionalView.vue` com cards, tabela e filtro por estado preservado na URL.
- `frontend/src/layouts/AppLayout.vue` com navegação para a tela operacional.
- CI verde antes de qualquer mudança de draft para pronto.

Refs #46