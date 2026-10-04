# Enforcement SDD no merge governado — Requisitos

## Requisito 1 — validação no SHA exato da PR
O workflow `Governed Merge Queue` deve executar o SDD Gate diretamente sobre o `head_sha` corrente da Pull Request e contra a base real declarada pela própria PR.

## Requisito 2 — falha fechada
Falha no SDD Gate deve tornar o workflow `Governed Merge Queue` não verde e impedir elegibilidade no caminho `Governed PR Automation`.

## Requisito 3 — rastreabilidade
A decisão consolidada da fila deve registrar o resultado do contrato SDD junto dos demais resultados usados para decidir elegibilidade.

## Critérios de aceite (Acceptance Criteria)
1. O job `sdd-contract` usa o SHA exato resolvido para a PR.
2. O job busca a base real da PR e executa `scripts/sdd_gate.py` com `--base-ref` e `--head-sha`.
3. O `merge-queue-gate` depende explicitamente de `sdd-contract`.
4. Resultado SDD diferente de `success` torna a avaliação de CI vermelha e impede elegibilidade.
5. Teste automatizado comprova a presença do vínculo no workflow.
6. O Pre-PR Readiness do HEAD desta alteração deve passar antes da abertura da PR.
