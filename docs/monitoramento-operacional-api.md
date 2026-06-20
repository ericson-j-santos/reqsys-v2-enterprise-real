# API — Monitoramento Operacional

## Endpoint

`GET /monitoramento-operacional`

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

Refs #46
