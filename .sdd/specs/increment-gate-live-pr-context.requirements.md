# Increment Gate — contexto vivo do PR — Requisitos

## Contexto

O job `increment-gate-on-open` do workflow `governed-pr-automation` infere o tipo de
incremento a partir de `github.event.pull_request`, que é um retrato congelado no instante
da abertura. Fluxos automatizados que criam o PR e só depois preenchem corpo e aplicam a
label chegam ao gate sem nenhum sinal declarado e caem no default `new_front` — bloqueado
em `state_yellow`. A decisão passa a refletir a latência do fluxo de abertura, não a
intenção real do incremento.

## Requisito 1 — inferência sobre o estado atual do PR

O gate de abertura deve reler título, corpo, labels e head_ref do estado atual do PR antes
de inferir o `increment_type`, usando o payload do evento apenas como fallback.

## Requisito 2 — degradação controlada

A releitura nunca pode transformar uma indisponibilidade de API em falha do gate. Sem
token, sem repositório ou sem número de PR, e em qualquer erro de API, o gate mantém o
payload do evento e prossegue.

## Requisito 3 — rastreabilidade da origem do contexto

A decisão deve declarar de qual fonte veio o contexto avaliado, e essa origem deve aparecer
no artifact de evidência e no comentário publicado no PR.

## Requisito 4 — preservação das regras de governança

Nenhuma regra de decisão é alterada: tipos permitidos, bloqueio de nova frente, exigência de
referência para `gap_fix` e o gate obrigatório de merge permanecem inalterados. A mudança
altera apenas de onde o contexto do PR é lido.

## Requisito 5 — testes independentes de dado vivo

Os testes do gate não podem depender do backlog vivo do repositório, sob pena de alternarem
entre verde e vermelho conforme gaps são abertos ou resolvidos.

## Critérios de aceite (Acceptance Criteria)

1. QUANDO o PR é avaliado com corpo vazio e sem label ENTÃO a inferência DEVE resultar em
   `new_front` com `inference_source=default:new_front` — reprodução do defeito.
2. QUANDO `--refresh-pr` está ativo e o PR vivo declara a label `increment:gap_fix` ENTÃO a
   inferência DEVE resultar em `gap_fix` com `pr_context_source=live_api`, ainda que o
   payload do evento esteja vazio.
3. SE não houver token, repositório ou número de PR ENTÃO o gate DEVE registrar
   `pr_context_source=live_api_skipped:missing_repo_pr_or_token` e concluir sem exceção.
4. SE a chamada de API falhar ENTÃO o gate DEVE registrar `pr_context_source=live_api_failed`,
   emitir aviso em stderr e decidir com o payload do evento.
5. A resposta da API DEVE ser normalizada com tolerância a `body`, `labels` e `head` nulos.
6. A decisão, o artifact e o comentário do PR DEVEM expor `pr_context_source`.
7. Um `gap_fix` inferido sem referência DEVE ser bloqueado com `gap_fix_sem_referencia`
   quando não há gap ativo no backlog, e permitido como `gap_fix_generico` quando há —
   ambos os ramos verificados sob isolamento, sem leitura do backlog vivo.
8. A repetição com a mesma entrada DEVE produzir a mesma decisão.
