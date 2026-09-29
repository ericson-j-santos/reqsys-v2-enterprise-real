# Traceability Graph Projection — Requisitos

## Objetivo

Expor uma projeção read-only da rastreabilidade já persistida pelo ReqSys, sem criar banco, catálogo ou fonte de verdade paralela.

## Requisitos

1. O grafo deve partir de um requisito canônico existente.
2. A projeção deve reutilizar somente fontes atuais: `Requisito`, `AgileWorkItem`, `VinculoGit` e evidência de CHANGE já persistida.
3. O endpoint deve representar vínculos de requisito, SDD, PR, commit/SHA, CI, deploy e evidência runtime quando existirem.
4. A leitura não pode gravar, atualizar ou duplicar nenhum registro.
5. A saída deve ser determinística: duas leituras sem alteração das fontes retornam o mesmo grafo.
6. Evidência só pode ser marcada como `verified` quando CI estiver em `success`, `runtime_sha == head_sha` e o status runtime for `PASSED` ou `ROLLED_BACK`.
7. SHA divergente deve permanecer visível apenas como diagnóstico rejeitado e nunca como evidência válida.
8. `FAILED` deve permanecer visível apenas como diagnóstico rejeitado e nunca como evidência válida.
9. Requisito inexistente deve retornar 404.
10. Este incremento não executa merge, deploy, promoção, alteração de segredo, criação de infraestrutura ou mutação em produção.

## Controles negativos

- Persistir diretamente uma linha legada/corrompida com `runtime_sha != head_sha` deve resultar em `rejected`.
- Evidência com status `FAILED` deve resultar em `rejected`.
- A leitura repetida não pode aumentar contagens nas tabelas de origem.

## Critérios de aceite

1. GET `/v1/rastreabilidade/requisitos/{id}/grafo` percorre requisito → SDD/PR/SHA → CI → deploy → runtime para um caso positivo.
2. O caso positivo marca exatamente uma evidência como válida.
3. O controle de SHA divergente produz zero evidências válidas e registra `runtime_sha_mismatch`.
4. O controle de status `FAILED` produz zero evidências válidas.
5. Replay da mesma leitura retorna payload idêntico e a leitura independente do banco confirma ausência de mutação.
6. Os testes executam via API FastAPI real sobre banco SQLite real de teste, sem mock do serviço de projeção.
7. Pre-PR Readiness deve ficar verde no HEAD exato antes da abertura da PR.
