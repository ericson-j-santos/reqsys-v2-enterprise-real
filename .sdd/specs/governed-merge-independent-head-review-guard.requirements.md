# Hotfix — impedir merge governado sem revisão independente vigente

## Contexto
Issue #2117, incidente PRs #3123 e #3125 em 03/11/2026. As duas foram integradas sem uma revisão `APPROVED` de identidade independente identificada pela API. O merge é atribuído à conta proprietária via GitHub web-flow: **não há prova de que os workflows de auto-merge tenham causado a integração**. O reparo aqui fortalece apenas os dois caminhos automatizados.

## Aceite
1. `Governed PR Automation` (CI-driven, recuperação de draft e dispatch manual) e `Autonomous Delivery Cycle` exigem pelo menos uma revisão `APPROVED` submetida por pessoa distinta do autor, com `commit_id` idêntico ao SHA alvo.
2. `CHANGES_REQUESTED` vigente, comentários, bot, autoaprovação ou aprovação antiga bloqueiam.
3. Atualizações concorrentes de HEAD bloqueiam antes da chamada de merge; a revisão é relida imediatamente antes de mutar.
4. Nenhum bypass de labels, checks, CI, E2E, SHA, revisão, branch protection, segredo, deploy ou custo.
5. Testes positivos e negativos de contrato detectam ausência do guard na automação, inclusive tentativa de promover draft recuperado.
6. O bloqueio de merge manual/por outro token exige branch protection/regras institucionais: **este hotfix não a substitui**.
7. A prova real de E2E em Power Platform DEV continua pendente e não pode ser inferida de CI verde ou revisão.
8. Pre-PR `READY_FOR_PR` deve ser validado na branch e no SHA exatos antes da PR draft; depois, CI, Validator independente, readback e revisão.

## Escopo
`.github/workflows/governed-pr-automation.yml`, `.github/workflows/autonomous-delivery-cycle.yml`, `tests/test_governed_pr_automation_dispatch_contract.py` e estes dois contratos SDD. Não altera `main` diretamente nem configura permissões.
