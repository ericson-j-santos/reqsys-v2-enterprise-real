# API — Monitoramento Operacional

## Endpoint

`GET /monitoramento-operacional`

No frontend Vite, a chamada usa `/api/monitoramento-operacional`, permitindo que o proxy remova o prefixo `/api` e encaminhe para o backend.

## Objetivo

Retornar snapshot operacional do ReqSys com envelope padrão, estado geral, sinais dinâmicos, correlação, próximos passos, critérios de fechamento e estimativas de tempo operacional.

## Versão do contrato

`schema_version = 1.2.0`

A versão 1.2.0 preserva `modo_coleta` e `coleta_detalhes` da arquitetura atual e acrescenta rastreabilidade de ação/fechamento, agregados de criticidade/prontidão e `tempo_operacional`.

## Campos principais

- `schema_version`
- `correlation_id`
- `coletado_em`
- `ambiente`
- `modo_coleta`
- `coleta_detalhes`
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

## Item monitorado

Além dos campos de estado, severidade e origem, cada item pode expor:

- `proximo_passo`
- `criterio_de_fechamento`
- `pronto_para_merge`
- `bloqueante`
- `detalhes`

## Tempo operacional

O bloco `tempo_operacional` contém estimativas para priorização:

- `previsao_proxima_acao`
- `eta_proxima_verificacao_minutos`
- `tempo_medio_proxima_acao_minutos`
- `tempo_medio_resolucao_horas`
- `tempo_medio_review_minutos`
- `sla_operacional_minutos`

Esses valores são estimativas operacionais e não substituem evidência real de CI, revisão, runtime ou entrega.

## Regras

1. `bloqueado` prevalece sobre os demais estados.
2. Lista vazia retorna `desconhecido`.
3. CI verde é condição necessária, mas não suficiente.
4. O frontend não consulta serviços externos diretamente.
5. O snapshot não expõe secrets, payloads sensíveis ou dados pessoais.
6. `frentes_criticas` e `itens_prontos_para_merge` são derivados dos próprios itens, sem valores fixos.
7. Pendências devem informar próximo passo e critério objetivo de fechamento.
8. O modo de coleta continua sendo `live`, `hibrido` ou `preview` conforme as fontes disponíveis.

## Evidências esperadas

- `backend/tests/test_monitoramento_operacional.py` valida contrato, correlação, agregados derivados, próximos passos, critérios e tempo operacional.
- CI deve ficar verde no HEAD atual.
- Evidência antiga não pode ser usada para promover um SHA diferente.

Refs #30 #31 #32 #33 #46
