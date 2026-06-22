# ReqSys — Email Operations Center v1

## Objetivo

Criar uma camada operacional governada para envios de e-mail, separando a entrega real do controle operacional.

Esta versao implementa o nucleo testavel de:

- fila operacional;
- retries;
- dead-letter queue;
- replay;
- timeline;
- metricas;
- semaforo de severidade;
- rastreabilidade por `correlation_id`.

## Problema que resolve

O envio MIME HTML resolve a montagem visual do e-mail, mas ainda nao resolve a operacao corporativa completa.

Sem um centro operacional, faltam:

- saber o que esta pendente;
- saber o que falhou;
- repetir uma entrega de forma controlada;
- auditar timeline por `correlation_id`;
- criar dashboard de saude operacional;
- separar erro temporario de falha definitiva.

## Componentes implementados

| Componente | Responsabilidade |
|---|---|
| `EmailDeliveryRequest` | Entrada governada de envio |
| `EmailDeliveryGateway` | Contrato para providers reais/fake |
| `EmailOperationsCenter` | Orquestracao de fila, retry, DLQ e replay |
| `InMemoryEmailOperationsRepository` | Persistencia em memoria para CI/demos |
| `FakeEmailDeliveryGateway` | Adapter fake deterministico para testes |
| `EmailOperationsMetrics` | Metricas consolidadas |
| `EmailOperationEvent` | Timeline operacional auditavel |

## Estados canonicos

| Status | Significado |
|---|---|
| `QUEUED` | Solicitacao enfileirada |
| `PROCESSING` | Tentativa em execucao |
| `SENT` | Envio confirmado pelo provider |
| `RETRY_SCHEDULED` | Falha temporaria com nova tentativa pendente |
| `DEAD_LETTER` | Tentativas esgotadas; requer acao/replay |
| `FAILED` | Reservado para falhas nao recuperaveis futuras |
| `REPLAYED` | Operacao retirada da DLQ para nova tentativa |

## Severidade operacional

| Severidade | Uso |
|---|---|
| `INFO` | Fluxo normal |
| `WARNING` | Retry ou replay |
| `CRITICAL` | DLQ / esgotamento de tentativas |

## Criterios de aceite implementados

- [x] Enfileirar solicitacao.
- [x] Processar proxima solicitacao.
- [x] Registrar sucesso.
- [x] Agendar retry em falha temporaria.
- [x] Mover para DLQ quando esgotar tentativas.
- [x] Permitir replay da DLQ.
- [x] Expor timeline por operacao.
- [x] Expor metricas consolidadas.
- [x] Cobrir fluxo com testes unitarios sem credenciais.

## Validacao automatizada

Arquivo de testes:

```bash
backend/tests/test_email_operations_center.py
```

Cobertura esperada:

- fila;
- sucesso;
- retry;
- DLQ;
- replay;
- rejeicao de replay invalido;
- validacao minima da request;
- timeline;
- metricas.

## Limitacoes da v1

Esta versao ainda nao possui:

- persistencia em banco;
- worker assíncrono;
- endpoint REST;
- dashboard visual;
- provider real plugado;
- agendamento temporal real de retry;
- DLQ persistente entre reinicios.

Esses pontos devem entrar em incrementos posteriores.

## Proximo incremento recomendado

### Email Operations Center v1.1 — Persistencia e API

Adicionar:

- tabela `email_operations`;
- tabela `email_operation_events`;
- repository SQL/SQLite;
- endpoints REST:
  - `POST /email-operations/enqueue`;
  - `POST /email-operations/process-next`;
  - `POST /email-operations/{id}/replay`;
  - `GET /email-operations/metrics`;
  - `GET /email-operations/{id}/timeline`;
- dashboard operacional com semaforo.

## Governanca

Todo provider real deve garantir:

- mascaramento de destinatarios em logs;
- nao logar token, segredo, refresh token ou MIME bruto sensivel;
- `correlation_id` obrigatorio;
- status de entrega registrado;
- `provider_message_id` armazenado quando disponivel;
- timeout e retry configuraveis;
- evidencia de falha sem vazar credenciais.
