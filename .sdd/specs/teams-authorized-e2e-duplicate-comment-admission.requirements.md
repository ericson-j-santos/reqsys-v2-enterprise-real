# Admissão governada de dois comandos físicos DEV

## Contexto
Dois comentários de proprietário distintos podem gerar dois despachos físicos para o mesmo modo. Ocorreu no Teams DEV e no canário Worker Pool #38487141475, seguido por um segundo run #38487187632 cancelado. A concorrência por ID de comentário evita perda de eventos mas não deduplica o alvo.

## Aceite
1. O controle de 120 segundos se aplica **somente** aos comandos fixos `/reqsys run pc24x7-teams-e2e-dev` e `/reqsys run pc24x7-worker-pool-candidate-canary-dev`.
2. O ID canônico mais antigo é admitido; o comentário posterior dentro da janela é suprimido **antes** de despachar um novo workflow, mesmo quando os gateways executam em ordem inversa.
3. Ler somente comentários **do proprietário** e do comando literal na issue #1705 com paginação; exigir readback único de ID, timestamp UTC, autor e SHA principal válido; comentários não autorizados e API ausente/inconsistente falham fechado. Um comentário de terceiro não pode suprimir comando legítimo.
4. Preservar `github.event.comment.id` no grupo de concorrência, `cancel-in-progress=false`, allowlist do ator, issue e destino. Não cancelar o run canônico nem mudar outros comandos.
5. A duplicata deve produzir artifact sanitizado com `duplicate_suppressed`, ID de comentário canônico e SHA esperado; sem token ou dados físicos.
6. Testes: positivo, duplicata reversa, janela expirada, comando trocado, entrada arbitrária e readback incompleto. Manter regressão Teams e bloqueio do canário quando nenhum gate válido existir.
7. Pre-PR, SDD, Security, CI e readback na revisão exata precedem merge. Não gerar dois canários reais para demonstrar duplicidade.
8. Esta proteção é janela temporal, não deduplicação durável por `source_sha`. Uma reexecução após a janela depende de nova pré-condição material comprovada.

## Limites
Somente DEV; nenhum deploy, troca da API legada, read/write de SQLite vivo, claim, requeue, segredo, produção, HML/STG ou alteração de permissões.
