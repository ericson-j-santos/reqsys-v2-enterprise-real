# Requisitos — Workflow Efficiency no artefato canônico

## Problema
O run 39607481863 homologou negativamente o artifact `ops-dashboard-static` do run 39607403674: o HTML existia, mas `cards.workflow_efficiency` e `links.workflow_efficiency` não estavam no índice JSON.

## Requisitos
1. O produtor principal deve calcular Workflow Efficiency com dados de execuções reais de PRs coletados pela API oficial do GitHub; fixtures sintéticas são permitidas apenas nos testes.
2. A ausência de coleta, amostra de PRs vazia ou contrato-fonte inválido deve bloquear a publicação. Não inferir pontuação real de entrada ausente.
3. O índice canônico deve integrar o card, seu link local e o mesmo score do contrato-fonte antes do empacotamento.
4. O HTML deve manter um único card visual e a execução report-only, sem chamadas externas no navegador ou alterações em workflows protegidos.
5. Antes do upload, a homologação deve verificar HTML, índice JSON, fonte empacotada, amostra e consistência de pontuação; o gate pós-download continua independente.
6. Nenhuma permissão administrativa, segredo novo, deploy, publicação em produção ou cobrança incremental adicional é autorizada.

## Critérios de aceite
- `tests/test_ops_dashboard_workflow_efficiency_integration.py` confirma a ordem coleta → enriquecimento → injeção → empacotamento → homologação → upload.
- `tests/test_homologate_workflow_efficiency_artifact.py` aprova o contrato completo e bloqueia card ausente, fonte ausente, fonte sem medição, pontuação divergente e JSON estruturalmente inválido.
- A geração real da fonte ocorre no mesmo run produtor via API GitHub; quando houver amostra, `source_available=true` e `pr_sample_count>0`.
- O `ops-dashboard-static` real contém `index.html`, `data/runtime-executive-index.json` e `data/ci-workflow-efficiency-dashboard.json`.
- A homologação deve ser comprovada por download independente do artifact, no SHA final, com `decision=HOMOLOGATED`; antes desse resultado, o estado permanece parcial/bloqueado.
- `Pre-PR Readiness Gate` e demais checks obrigatórios devem executar no HEAD exato antes de abrir/integrar PR.

## Rollback
Reverter somente o incremento desta branch, sem contornar homologação, proteções de merge ou validações existentes.
