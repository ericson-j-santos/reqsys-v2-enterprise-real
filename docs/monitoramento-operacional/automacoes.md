# Monitoramento Operacional — Automacoes

## Objetivo

Definir o painel operacional de automacoes criticas do ReqSys.

## Campos obrigatorios

| Campo | Descricao |
|---|---|
| automation_id | Identificador tecnico |
| nome | Nome funcional |
| status | Estado canonico |
| frequencia | Periodicidade |
| ultima_execucao | Ultima execucao comprovada |
| proxima_execucao | Proxima execucao prevista |
| duracao_ms | Duracao |
| correlation_id | Identificador da execucao |
| head_sha | SHA observado quando aplicavel |
| run_id | Identificador da execucao no provedor quando aplicavel |
| idempotency_key | Chave de repeticao segura quando aplicavel |
| retry_count | Tentativas realizadas |
| canal | Canal operacional |
| evidencia | Referencia da evidencia |
| recomendacao | Proxima acao recomendada |

## Health score

Pontuacao recomendada:

- 100: executado, entregue e confirmado;
- 80: executado e entregue, mas sem confirmacao posterior;
- 60: executado, mas entrega pendente;
- 40: ativo, mas sem ultima execucao;
- 20: falha recente sem retry concluido;
- 0: bloqueado ou estado desconhecido.

## Drill-down

Cada linha do painel deve abrir o detalhe da execucao com:

- timeline de progresso material;
- payload sanitizado;
- evidencias;
- falhas;
- retries e replays idempotentes;
- links relacionados;
- decisao recomendada.

## Regra de maturidade

Automacao sem evidencia nao pode ser classificada como pronta para producao. Heartbeat, lease renovado ou polling sem mudanca material nao elevam o estado de maturidade.
