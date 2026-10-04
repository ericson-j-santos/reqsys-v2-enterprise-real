# Runbook — Runtime Operational Health

## Objetivo

Validar periodicamente a disponibilidade de uma URL pública do ReqSys, registrar evidência operacional e criar base para observabilidade viva.

Este incremento representa a fundação de **Runtime Observability Foundation** dentro da Operational Runtime Governance Platform.

## Workflow

```text
.github/workflows/runtime-operational-health.yml
```

Nome no GitHub Actions:

```text
Runtime Operational Health
```

## Acionamentos

| Tipo | Uso |
|---|---|
| `workflow_dispatch` | Execução manual por operador. |
| `schedule` | Execução automática a cada 30 minutos. |

## Inputs manuais

| Input | Obrigatório | Padrão | Descrição |
|---|---:|---|---|
| `target_url` | Sim | `https://reqsys-app.fly.dev` | URL HTTPS alvo do health check. |
| `environment` | Sim | `production` | Ambiente avaliado. |

## Guardrails

- Apenas URLs HTTPS são permitidas.
- O workflow não executa comandos no runtime.
- O workflow não lê nem imprime secrets.
- O resultado é publicado como artifact.
- Falha HTTP `4xx`, `5xx` ou `000` reprova o job.
- HTTP `2xx` ou `3xx` é considerado saudável.

## Evidência operacional

Artifact:

```text
runtime-operational-health
```

Arquivos:

| Arquivo | Descrição |
|---|---|
| `runtime-health.json` | Resultado estruturado do health check. |
| `summary.md` | Resumo executivo para leitura rápida. |
| `response-body.txt` | Corpo retornado pela URL alvo para diagnóstico básico. |

## Interpretação

| Status | Condição | Ação |
|---|---|---|
| `healthy` | HTTP 2xx/3xx | Manter observação. |
| `unhealthy` | HTTP 4xx/5xx/000 | Verificar logs, deploy, DNS, Fly.io e últimas mudanças. |

## Procedimento de resposta

1. Validar artifact `runtime-operational-health`.
2. Abrir `summary.md`.
3. Verificar `http_status` e `response_time_ms`.
4. Se `unhealthy`, consultar workflow `Fly.io Governed Command Center` com `status` e depois `logs`.
5. Registrar evidência no PR, issue ou relatório operacional.

## Relação com Fly.io Governed Command Center

Este workflow apenas observa. Para ação operacional, usar:

```text
.github/workflows/fly-governed-command-center.yml
```

Ordem recomendada:

```text
Runtime Operational Health → Fly status → Fly logs → correção governada → nova validação de health
```

## Próximo incremento recomendado

- Persistir histórico de health checks.
- Expor painel no ReqSys Runtime Center.
- Adicionar correlation_id por execução.
- Integrar leitura de artifacts pelo Actions Center.
- Criar semáforo operacional por ambiente.
- Disparar alertas condicionais quando health falhar.
