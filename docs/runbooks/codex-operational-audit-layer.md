# Runbook — Codex Operational Audit Layer

## Endpoint

```text
GET /v1/codex/operational-summary?limite=10
```

## Objetivo

Consultar indicadores operacionais do Codex Governado sem depender de logs brutos.

## Indicadores

- total de execucoes;
- total de concluidos;
- total de bloqueados;
- publicacoes ReqSys;
- taxa de bloqueio;
- latencia media;
- score medio de confianca;
- distribuicao por provider;
- ultimas execucoes por `correlation_id`.

## Validacao

```bash
cd backend
python -m pytest tests/test_codex_governado.py -v
```

## Criterio de pronto

- Tabela `codex_auditoria` criada no boot da aplicacao.
- Analises gravam auditoria persistente.
- Endpoint retorna agregados.
- Testes cobrem persistencia e resumo operacional.
