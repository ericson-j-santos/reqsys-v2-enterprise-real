# Admissão governada do ensaio Worker Pool 1.4 → 1.2

## Objetivo
Corrigir a incompatibilidade observada em [Gateway #38496349534](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/38496349534): o workflow aceita o comando exato do ensaio físico, mas a CLI de admissão ainda não o reconhece. A PR #2582 já foi integrada, portanto a correção será um incremento pequeno e separado, sem reabrir a PR integrada.

## Escopo
- Incluir exclusivamente `/reqsys run pc24x7-worker-pool-real-restore-dev` na allowlist do validador existente.
- Preservar o contrato de autor, issue #1705, SHA, janela 120 s, leitura dos comentários e ausência de dispatch para entrada inválida.
- Reutilizar o workflow atual, sem novo scheduler, tarefa, runner, serviço, segredo ou contêiner.
- O código deste incremento não realiza execução física: somente restaura o gate do despacho governado.

## Critérios de aceite
1. A CLI aceita o comando exato enviado pelo owner na issue #1705 e escreve recibo de admissão vinculado ao SHA.
2. Dois comentários válidos próximos mantêm só a primeira admissão; repetição do mesmo evento é determinística.
3. Autor diferente, comando inválido, ausência do comentário atual e divergência com o corpo da solicitação falham antes de qualquer dispatch.
4. A allowlist Python e a rota fixa do workflow permanecem consistentes, com testes positivos, negativos e de regressão.
5. Pre-PR Readiness e checks de CI efetivamente executados no HEAD atual, branch sincronizada e merge somente por gates do GitHub.
6. Após merge, um único despacho físico usa o Gateway existente, sem tocar API 1.2 ativa; só considerar sucesso E2E após artefato, rollback em cópia, cleanup e readback independentes.

## Restrições
Sem novos privilégios, sem mudança de host, sem deploy/cutover, sem claim/requeue, sem alteração de token/banco ativo; `cutover_ready=false` até aceite da política canônica.
