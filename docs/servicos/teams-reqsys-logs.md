# Fluxo de logs do ReqSys para o Microsoft Teams

## Objetivo

Enviar ao Teams um resumo operacional seguro quando workflows críticos do ReqSys falharem, preservando o log bruto no GitHub Actions e evitando vazamento de credenciais ou dados pessoais.

## Fluxo

1. Um workflow monitorado termina com conclusão diferente de `success`.
2. `Notify Teams - ReqSys Logs` consulta os jobs e etapas da execução pelo GitHub Actions API.
3. `scripts/notify_reqsys_logs_teams.py` remove tokens, secrets, senhas, chaves e endereços de e-mail.
4. O script monta um Adaptive Card 1.2 estruturado e tenta o webhook adaptável validado pelo ReqSys.
5. Se a rota adaptável não estiver configurada ou falhar, o Teams Messaging Gateway permanece como fallback.
6. Um artifact JSON registra correlation ID, hashes da mensagem e do cartão e resultado sanitizado da entrega, sem armazenar o corpo do cartão nem o texto bruto dos logs.

## Layout do Adaptive Card

O cartão apresenta:

- cabeçalho `ReqSys · Alerta operacional`;
- severidade e ambiente em destaque;
- resumo em bloco próprio;
- `FactSet` para status, severidade, ambiente, origem, workflow, run ID e correlation ID;
- até oito falhas visíveis para evitar cartões excessivamente longos;
- contador de itens adicionais quando houver mais falhas;
- botão **Abrir execução no GitHub**;
- aviso de que os logs completos permanecem no GitHub Actions.

## Rotas de entrega

### Primária

Usa:

- `TEAMS_WEBHOOK_URL`;
- `TEAMS_WEBHOOK_RECIPIENT`.

O payload define `renderMode=adaptive-card`, `adaptiveCard` e `adaptiveCardJson`.

### Fallback

Mantém:

- política dinâmica `reqsys-operations`;
- `delivery_mode=all`;
- `TEAMS_GATEWAY_DESTINO_ID` somente como compatibilidade de transição.

A ausência da rota primária não interrompe a notificação padrão, salvo uso explícito de modo estrito.

## Workflows monitorados

- `CI — ReqSys v2 Enterprise`
- `Main Post-Merge Validation`
- `Fly Runtime P0`
- `Runtime Health Validator`
- `Repository Health Watchdog`

## Destinatários

A política dinâmica `reqsys-operations` continua preparada para múltiplos destinatários. A rota Adaptive Card direta usa o destinatário do webhook já configurado. O gateway permanece disponível como fallback e preserva a política dinâmica.

## Execução manual

Use **Actions → Notify Teams - ReqSys Logs → Run workflow** e informe ambiente, severidade, resumo, detalhes e URL de evidência.

## Segurança

- Não envia stack trace ou log bruto ao Teams.
- Não imprime secrets do GitHub ou do gateway.
- Remove padrões de token, senha, secret, API key e e-mail.
- Aceita botão de evidência somente para URL HTTPS em `github.com`.
- Limita a quantidade de falhas renderizadas no cartão.
- Não persiste o corpo do Adaptive Card no artifact.
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
