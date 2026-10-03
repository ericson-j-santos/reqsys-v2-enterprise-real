# Observabilidade — Padrão Enterprise

## Objetivo

Padronizar logs, métricas, tracing, auditoria e analytics operacional no ReqSys.

## Regras obrigatórias

- Todo request deve possuir `correlation_id`.
- Logs devem ser estruturados em JSON.
- Nenhum log pode expor senha, token, CPF, segredo, connection string ou PII.
- Toda integração crítica deve possuir:
  - duração;
  - status;
  - origem;
  - destino;
  - tentativa;
  - erro resumido.

## Campos mínimos de log

```json
{
  "timestamp": "2026-06-20T20:00:00Z",
  "level": "INFO",
  "service": "reqsys-api",
  "environment": "production",
  "correlation_id": "uuid",
  "operation": "consultar_requisitos",
  "duration_ms": 120,
  "status": "success"
}
```

## Métricas mínimas

- tempo médio de resposta;
- taxa de erro;
- falhas por integração;
- throughput;
- filas pendentes;
- falhas de autenticação;
- consultas IA sem fonte;
- uso por ambiente.

## Analytics operacional

Aplicar drill-down:

```text
Indicador → gráfico → detalhe → log correlacionado → ação operacional
```

## Ambientes

Todos os logs e métricas devem identificar:

- `dev`
- `homologacao`
- `production`

## Alertas críticos

Alertar automaticamente quando ocorrer:

- falha de autenticação;
- CI quebrado;
- erro em integração crítica;
- aumento abrupto de erro;
- timeout elevado;
- consulta IA sem fonte;
- perda de rastreabilidade.
