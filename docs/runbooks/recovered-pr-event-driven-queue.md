# Fila recuperada event-driven

## Fluxo

```text
CI termina
→ PR CI Watch remedia falha transitória
→ falha técnica determinística elegível: Ollama CI Triage → Codex Worker Pool na mesma branch/SHA
→ falha persistente ou não elegível: checkpoint no PR + Teams
→ Repository Governance Agent sincroniza a recuperada mais antiga
→ Governed Merge Queue valida HEAD/base
→ draft recuperado verde vira ready, sem merge
→ ready_for_review reexecuta gates
→ GMQ verde novamente
→ squash merge com SHA esperado
→ governed_post_merge_validation
→ Actions Dispatcher grava checkpoint e dispara próxima PR
```

## Fonte de verdade

- GitHub PR, HEAD, checks e artifacts: estado canônico.
- Comentário de checkpoint no PR: estado durável.
- Teams: notificação.
- ChatGPT: watchdog/interface opcional.

## Correção governada

`Ollama CI Triage` já é o executor de triagem para falhas de `CI — ReqSys v2 Enterprise`, `CI Enterprise Fast` e `Pre-PR Readiness Gate`. Em falha técnica com confiança suficiente e evidência determinística, ele enfileira o Codex Worker Pool com `target_branch` da PR e `base_sha` igual ao HEAD analisado. O worker permanece sujeito a idempotência, leitura independente e proteção contra branch protegida. Falhas sensíveis ou não elegíveis continuam bloqueadas e notificadas.

## Segurança

- sem fechamento/recriação de PR;
- sem force-push;
- sem merge no mesmo ciclo que converte draft para ready;
- sem deploy/promoção;
- sem workflow novo.

## Notificação de bloqueio

Quando o `PR CI Watch` termina vermelho em uma PR `ci:recuperado`, o workflow existente `Notify Teams - ReqSys Logs` registra um comentário idempotente no PR e envia o alerta usando `TEAMS_WEBHOOK_URL`. O gateway Fly permanece desativado; não existe fallback para Fly.io.
