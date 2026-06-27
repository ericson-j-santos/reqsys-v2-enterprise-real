# Runbook — Runtime Validator & Auto-Remediation Engine

## Objetivo
Operar health checks, validação de workflows, incident detection, stability score, remediação segura e timeline operacional do ReqSys Enterprise.

## Endpoints
- `GET /api/runtime-validator/health`: coleta checks de API, banco, cache e evidências.
- `POST /api/runtime-validator/workflows/validate`: valida jobs obrigatórios, falhas e evidências.
- `GET /api/runtime-validator/incidents`: detecta incidentes a partir dos sinais atuais.
- `POST /api/runtime-validator/remediations`: cria remediação governada com retries, rollback e circuit breaker.
- `GET /api/runtime-validator/timeline`: lista eventos operacionais recentes.
- `GET /api/runtime-validator/dashboard`: consolida status, score, incidentes, timeline e governance events.

## Operação segura
1. Sempre enviar `X-Correlation-ID` ou `X-Request-ID`.
2. Usar `mode=dry_run` antes de qualquer execução.
3. Validar `rollback_plan` retornado antes de executar mudanças reais.
4. Bloquear rollback automático em produção até existir aprovação humana e evidência do último artefato estável.

## Exemplo
```bash
curl -H 'X-Correlation-ID: example-runtime-001' http://localhost:8000/api/runtime-validator/dashboard
```

## Persistência futura
A timeline curta atual é em memória. Para produção, persistir eventos em SQL Server/PostgreSQL e publicar sinais de baixa latência em Redis Streams.
