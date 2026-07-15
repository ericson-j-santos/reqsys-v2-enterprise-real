# OpenTelemetry Collector autocontido

O Collector recebe OTLP do serviço, aplica proteção de memória e batch, persiste a fila em volume isolado por ambiente e exporta para um backend OTLP configurado explicitamente.

## Execução local

```bash
APP_ENV=development \
OTEL_UPSTREAM_ENDPOINT=https://backend.example/v1/traces \
docker compose -f compose.collector.yml up -d
```

No serviço:

```bash
OTEL_TRACING_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

## Portas locais

- `4317`: OTLP gRPC;
- `4318`: OTLP HTTP;
- `8888`: métricas internas do Collector;
- `13133`: health check.

Todas as portas são publicadas somente em `127.0.0.1` no Compose. Em ambiente gerenciado, exponha apenas pela rede privada.

## Isolamento

Use uma instância e um volume por ambiente. O nome do volume inclui `APP_ENV`; credenciais de produção não devem ser reutilizadas em development ou staging.

## Detecção de perda de telemetria

Crie alertas sobre as métricas internas do Collector, principalmente:

- `otelcol_exporter_send_failed_spans` maior que zero;
- `otelcol_receiver_refused_spans` maior que zero;
- falha do endpoint `:13133`;
- uso de memória próximo do limite;
- fila persistentemente cheia ou sem redução.

A fila e o retry reduzem perda temporária, mas não substituem retenção no backend. O volume deve ter lifecycle e capacidade definidos por ambiente.

## Segurança

O container usa filesystem somente leitura, remove capabilities e ativa `no-new-privileges`. Tokens do backend devem ser fornecidos por secret do ambiente; nunca devem ser gravados no arquivo de configuração ou no repositório.
