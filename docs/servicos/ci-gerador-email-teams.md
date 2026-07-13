# CI — validação do gerador Email/Teams standalone

## Objetivo

Garantir que o gerador `tools/geradores/gerar_servicos_email_teams.py` continue capaz de materializar os dois serviços extraídos do ReqSys:

- `email-report-service`
- `teams-gateway-service`

## Workflow

```text
.github/workflows/standalone-services-generator-validation.yml
```

## Gates executados

1. `--dry-run` para validar o pré-check do gerador sem escrita.
2. Geração dos projetos em `/tmp/reqsys-standalone-services`.
3. Execução dos testes unitários embutidos nos projetos gerados.
4. Verificação contratual dos 9 arquivos esperados.
5. Verificação de contratos mínimos:
   - `X-Correlation-ID` no serviço de e-mail.
   - `dry_run` no serviço de e-mail.
   - `fallback_usado` no gateway Teams.
   - `webhook_payload` no gateway Teams.
   - sanitização de token em `provider_response`.
6. Upload do artifact `standalone-services-generated`.

## Decisão

Este gate evita que alterações futuras no gerador quebrem silenciosamente a extração dos serviços standalone. O artifact gerado serve como evidência reutilizável para homologação técnica.
