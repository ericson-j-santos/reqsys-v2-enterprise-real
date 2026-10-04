# Fila de PR orientada por eventos — sem ChatGPT Work

## Fluxo

CI do PR conclui
→ PR CI Remediation (workflow_run)
→ falha transitória: rerun allowlisted
→ falha determinística: labels/checkpoint
→ Ollama CI Triage (workflow_run em falha)
→ diagnóstico + Worker Pool quando elegível + comentário sanitizado
→ Governed Merge Queue verde
→ Governed PR Automation revalida HEAD/base/gates e faz merge protegido por SHA
→ push na main
→ Teams Commit Notification avisa PR integrado

## Notificações

Teams Commit Notification também observa Ollama CI Triage e PR CI Remediation.
O envio ocorre somente quando há mudança material. Se TEAMS_WEBHOOK_URL ou o destinatário não estiverem configurados, o workflow registra a ausência e não bloqueia o CI.

## Checkpoint canônico

A fonte de verdade permanece no GitHub: HEAD do PR, workflow runs, labels de CI, comentário sanitizado do Ollama CI Triage e merge SHA.
Assim qualquer chat futuro pode reconstruir o estado sem depender desta conversa.

## Papel do ChatGPT

ChatGPT não é scheduler nem broker de eventos desta fila. Pode ser usado a qualquer momento para consultar o GitHub, explicar o estado ou executar uma correção manual excepcional.

## Watchdog

O cron de PR CI Remediation permanece como rede de segurança. O caminho primário é workflow_run; a fila não espera o cron para reagir a um CI recém-concluído.
