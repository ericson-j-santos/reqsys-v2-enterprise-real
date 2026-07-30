# Fluxo de logs do ReqSys para o Microsoft Teams

## Objetivo

Enviar ao Teams um resumo operacional seguro quando workflows críticos do ReqSys falharem, preservando o log bruto no GitHub Actions e evitando vazamento de credenciais ou dados pessoais.

## Fluxo

1. Um workflow monitorado termina com conclusão diferente de `success`.
2. `Notify Teams - ReqSys Logs` consulta os jobs e etapas da execução pelo GitHub Actions API.
3. O script `scripts/notify_reqsys_logs_teams.py` remove tokens, secrets, senhas, chaves e endereços de e-mail.
4. O resumo é enviado ao Teams pelo Teams Messaging Gateway.
5. Um artifact JSON registra correlation ID, hash da mensagem e resultado da entrega, sem armazenar o texto bruto dos logs.

## Workflows monitorados

- `CI — ReqSys v2 Enterprise`
- `Main Post-Merge Validation`
- `Fly Runtime P0`
- `Runtime Health Validator`
- `Repository Health Watchdog`

## Destinatários

A política dinâmica `reqsys-operations` usa `delivery_mode=all`. Novos destinatários devem ser cadastrados na política, sem criar um secret por pessoa. `TEAMS_GATEWAY_DESTINO_ID` permanece apenas como fallback de transição.

## Execução manual

Use **Actions → Notify Teams - ReqSys Logs → Run workflow** e informe ambiente, severidade, resumo, detalhes e URL da evidência.

## Segurança

- Não envia stack trace ou log bruto ao Teams.
- Não imprime secrets do GitHub ou do gateway.
- Remove padrões de token, senha, secret, API key e e-mail.
- Usa permissões mínimas: `actions: read` e `contents: read`.
- Não altera ambiente, aplicação, banco ou produção.

## Validação local

```bash
python -m pytest tests/scripts/test_notify_reqsys_logs_teams.py -q
python scripts/notify_reqsys_logs_teams.py \
  --environment dev \
  --severity warning \
  --summary "Teste governado" \
  --details "Falha simulada" \
  --dry-run \
  --output reqsys-log-teams-evidence.json
```
