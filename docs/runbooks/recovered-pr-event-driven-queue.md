# Fila recuperada event-driven

## Fluxo

CI termina
→ PR CI Remediation reage imediatamente ao workflow_run
→ falha transitória allowlisted: rerun no mesmo HEAD
→ falha técnica determinística elegível: Ollama CI Triage → Codex Worker Pool na mesma branch/base_sha
→ falha persistente/não elegível: checkpoint no PR + Teams
→ Repository Governance Agent sincroniza a recuperada mais antiga
→ Governed Merge Queue valida HEAD/base
→ draft recuperado verde vira ready, sem merge
→ ready_for_review reexecuta gates
→ GMQ verde novamente
→ squash merge com SHA esperado
→ governed_post_merge_validation
→ Actions Dispatcher grava checkpoint e dispara próxima PR
→ push na main gera notificação do PR integrado

## Fonte de verdade

- GitHub PR, HEAD, checks, comments, labels e artifacts: estado canônico.
- Teams: canal de notificação imediata quando configurado.
- ChatGPT: interface/watchdog opcional; não é scheduler nem broker desta fila.

## Remediação

`PR CI Remediation` usa `workflow_run` como caminho primário e o cron apenas como contingência. O evento é limitado ao PR e HEAD do run; evento stale não altera labels nem reexecuta jobs. Se ainda existirem workflows pendentes, o PR não é marcado como recuperado.

`Ollama CI Triage` permanece responsável por falhas técnicas determinísticas elegíveis e pode enfileirar o Worker Pool na mesma branch com `base_sha` igual ao HEAD analisado. Segurança, governança e casos não elegíveis continuam fail-closed.

## Notificações

`Notify Teams - ReqSys Logs` mantém o alerta de bloqueio persistente da fila recuperada. `Teams Commit Notification` passa a consumir também a conclusão de `Ollama CI Triage` e `PR CI Remediation`, usando seus artifacts sanitizados; remediação sem mudança material é ignorada.

Quando um merge governado chega à `main`, o commit `governed CI-driven merge PR #N` é apresentado no Teams como PR integrado.

## Segurança

- sem fechamento/recriação de PR;
- sem force-push;
- sem merge no mesmo ciclo que converte draft para ready;
- sem deploy/promoção;
- sem workflow novo;
- sem dependência de ChatGPT Work.
