# Fila de PR orientada por eventos

## Objetivo

Remover o ChatGPT/Work do caminho crítico da fila de PRs do ReqSys e fazer o próprio GitHub reagir aos eventos de CI.

## Requisitos

1. PR CI Remediation deve reagir a workflow_run dos gates primários.
2. O agendamento periódico permanece apenas como watchdog de contingência.
3. O evento deve atuar somente no PR e HEAD associados ao workflow_run.
4. Evento de SHA antigo deve ser ignorado sem alterar labels ou reexecutar CI.
5. PR com workflow ainda pendente não pode receber estado recuperado.
6. Falhas determinísticas continuam sendo encaminhadas pelo Ollama CI Triage ao Worker Pool.
7. Falhas transitórias allowlisted podem ser reexecutadas pelo remediador.
8. Teams Commit Notification deve reagir a triagem/remediação concluídas e ao push de merge na main.
9. Notificação Teams deve ser emitida somente em mudança material; ausência de configuração não pode bloquear CI.
10. Nenhum workflow ativo novo deve ser criado.
11. Nenhuma etapa depende de ChatGPT Work ou de polling do chat.
12. Merge continua protegido pelo Governed PR Automation e SHA exato.

## Critérios de aceite

- O caminho primário reage a workflow_run dos gates de CI sem esperar o cron.
- O cron permanece apenas como watchdog.
- O PR e o HEAD do evento são revalidados antes de qualquer mutação.
- Eventos de SHA antigo não alteram labels nem disparam rerun.
- Workflows pendentes não marcam o PR como recuperado.
- Falhas técnicas elegíveis continuam indo para Ollama CI Triage e Worker Pool.
- Mudanças materiais são notificadas pelo Teams quando a integração estiver configurada.
- Merge permanece condicionado ao Governed Merge Queue e ao SHA exato.
- Nenhuma etapa depende de ChatGPT Work.
- Nenhum novo workflow ativo é criado.
