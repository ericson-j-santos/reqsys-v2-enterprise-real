# Fila recuperada event-driven

## Fluxo

```text
CI termina
→ PR CI Watch remedia falha transitória
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

## Limite

Falha determinística de código continua fail-closed até existir executor governado capaz de alterar o mesmo PR sem violar proteção de SHA.

## Segurança

- sem fechamento/recriação de PR;
- sem force-push;
- sem merge no mesmo ciclo que converte draft para ready;
- sem deploy/promoção;
- sem workflow novo.
