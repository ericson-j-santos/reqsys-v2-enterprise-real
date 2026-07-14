# Notificação de commits no Microsoft Teams

## Fluxo

`push em main` → `Teams Commit Notification` → `Teams Gateway autocontido` → webhook do Teams/Workflows.

## Configuração obrigatória

Cadastre no repositório o secret:

```text
TEAMS_WEBHOOK_URL
```

O valor deve ser a URL de gatilho HTTP de um fluxo do Power Automate (app Workflows) que receba `{to, title, content, signature, stampDate, correlationId}` e publique a mensagem no canal do Microsoft Teams. Este é o mesmo contrato de payload usado pela família de fluxos `robo_envia_teams*` já em produção neste tenant — reutilizar um desses fluxos (ou um clone) em vez de criar um novo com schema diferente.

## Validação

Após o merge, execute manualmente o workflow **Teams Commit Notification** usando `workflow_dispatch`. O job somente conclui com sucesso quando:

- o secret existe;
- o gateway passa no `self-test`;
- o endpoint retorna HTTP 2xx;
- o resultado contém `success=true`;
- o resumo registra HTTP e `correlation_id`.

O mesmo workflow será executado automaticamente nos próximos pushes para `main`.

## Segurança

- A URL não é registrada nos logs.
- O segredo não fica no código.
- O workflow possui somente permissão `contents: read`.
- Mensagens são construídas sem executar conteúdo proveniente da mensagem do commit.
