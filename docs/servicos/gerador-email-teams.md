# Gerador autocontido — Email Report Service e Teams Gateway Service

## Objetivo

Gerar dois projetos Python independentes a partir dos serviços existentes no ReqSys:

- `email-report-service`: geração de relatório HTML/texto, mensagem MIME multipart e envio SMTP com `dry_run`.
- `teams-gateway-service`: gateway de envio Microsoft Teams com rota `graph_delegado`, `webhook`, `graph_app_only`, fallback para webhook, `dry_run`, `correlation_id` e sanitização de tokens.

## Fonte funcional extraída

- `backend/app/services/email_mime_report_service.py`
- `backend/app/services/email_report_template.py`
- `backend/app/services/teams_gateway.py`
- `backend/app/schemas/teams_gateway.py`
- `backend/tests/test_teams_gateway_service.py`

## Como gerar

```bash
python tools/geradores/gerar_servicos_email_teams.py --force --run-tests
```

Saída padrão:

```text
artifacts/standalone-services/
├── email-report-service/
└── teams-gateway-service/
```

## Testes aplicados localmente antes da publicação

```text
email-report-service: 3 testes unitários OK
teams-gateway-service: 5 testes unitários OK
```

## Decisão técnica

O gerador materializa projetos autocontidos em Python puro, sem dependência obrigatória de FastAPI, SQLAlchemy, Pydantic, HTTPX, banco de dados ou `settings` globais do backend principal. Isso permite copiar, versionar, testar e evoluir os dois serviços como módulos independentes.