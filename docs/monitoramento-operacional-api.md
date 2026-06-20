# API — Monitoramento Operacional

## Endpoint

`GET /monitoramento-operacional`

## Objetivo

Retornar o snapshot operacional mínimo do ReqSys com estado geral, itens monitorados, ambiente, correlação e evidências para consumo pelo painel `/monitoramento-operacional`.

## Envelope

A resposta segue o envelope padrão da API ReqSys.

Campos principais em `data`:

- `schema_version`;
- `correlation_id`;
- `coletado_em`;
- `ambiente`;
- `resumo`;
- `itens`.

## Estados

- `verde`: aprovado.
- `amarelo`: pendência não bloqueante.
- `vermelho`: falha técnica ou funcional.
- `bloqueado`: risco crítico, conflito ou gate impeditivo.
- `desconhecido`: sinal indisponível.

## Regras

1. `bloqueado` prevalece sobre qualquer outro estado.
2. Lista vazia retorna `desconhecido`.
3. Item em andamento não deve ser tratado como pronto para merge.
4. CI verde é condição necessária, mas não suficiente.
5. O endpoint não deve expor credenciais, segredos, dados pessoais ou payloads sensíveis.

## Próximas integrações

- GitHub PRs.
- GitHub Actions.
- Validação pública.
- Gates de produção.
- GovBI IA.
- Planner.
- Dashboard Analítico.

Refs #46
