# ReqSys main — required checks nativos no ruleset

## Problema
O ruleset ativo 17998541 protege a default branch contra deleção, non-fast-forward e exige pull request, mas não possui regra required_status_checks. Isso permite que o enforcement nativo do GitHub dependa apenas dos workflows governados.

## Alvo
Materializar no ruleset existente, sem substituí-lo e sem criar bypass, os oito check run names canônicos definidos em config/required-checks-inventory-policy.json.

## Requisitos
1. Preservar name, target, enforcement, conditions, bypass_actors e todas as regras existentes.
2. Adicionar/substituir somente a regra required_status_checks.
3. Exigir strict_required_status_checks_policy=true.
4. Usar exatamente os oito recommended_required_contexts; nomes de workflow não são aceitos.
5. Ler novamente branch e ruleset após PUT; ausência ou divergência falha fechado.
6. Não aceitar bypass actor.
7. Não expor GH_TOKEN, GITHUB_TOKEN, PAT ou segredo em comando/evidência.
8. A execução administrativa deve passar por Session Launcher + Owner Risk3 Gateway e remover a autorização temporária ao final.
9. Não alterar produção, deploy, banco ou runtime da aplicação.

## Aceite
- ruleset 17998541 permanece active e targeting ~DEFAULT_BRANCH;
- deletion, non_fast_forward e pull_request permanecem presentes;
- required_status_checks contém os oito contextos canônicos e strict=true;
- main continua protected;
- readback independente gera artifact sanitizado;
- teste unitário prova preservação da regra pull_request e falha quando a lista de checks diverge.
