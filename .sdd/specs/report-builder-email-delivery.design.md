# Design — Report Builder Email Delivery

## Fluxo

```text
POST /v1/report-builder/reports/generate-and-email
        |
        v
autorização report_builder:send
        |
        v
PaginatedReportGenerateRequest (fail-closed)
        |
        v
gerar_paginated_report
        |
        v
EmailMessage + RDL attachment + correlation_id + SHA-256
        |
        +--> dry_run: sem escrita externa
        |
        v
sender_factory existente
        |
        +--> Microsoft Graph
        +--> SMTP
```

## Decisões

- **Menor incremento:** reutiliza geração e infraestrutura de e-mail existentes, sem introduzir novo runtime.
- **Fail-closed:** validação de e-mail, assunto e SQL ocorre antes de qualquer envio.
- **Observabilidade:** cada mensagem carrega `X-Correlation-ID` e `X-Report-SHA256`.
- **Sem segredo novo:** o endpoint usa somente configuração já resolvida pelo runtime.
- **Sem publicação Fabric:** gerar/enviar RDL é independente de criar/atualizar item no Fabric.
- **Estado de entrega verdadeiro:** Graph HTTP 202 e aceitação SMTP demonstram apenas recepção pelo provedor. A API retorna `accepted_by_provider` e indicadores `provider_accepted=true`, `recipient_delivery_confirmed=false`, `recipient_delivery_evidence=not_observed`; o `dry_run` mantém `planned` e nenhum envio.
- **E2E:** CI cobre o fluxo FastAPI com sender controlado e controles negativos; entrega real exige runtime configurado e readback independente do destinatário. Não inferir entrega pela resposta da API.
