# Teams ReqSys Logs v1.0.0

## Entrega

- Notificação automática de falhas dos workflows operacionais prioritários.
- Consulta read-only de jobs e etapas com erro no GitHub Actions.
- Sanitização de segredos e dados pessoais antes do envio.
- Política dinâmica `reqsys-operations` com suporte a múltiplos destinatários.
- Artifact de evidência com correlation ID e hash SHA-256 da mensagem.
- Execução manual governada para eventos fora dos workflows monitorados.

## Compatibilidade

Reutiliza `scripts/notificar_teams.py` e o Teams Messaging Gateway atual. O secret legado de destino continua apenas como fallback.

## Rollback

Reverter os arquivos desta versão ou desabilitar o workflow `Notify Teams - ReqSys Logs`. Nenhuma migração de banco é necessária.
