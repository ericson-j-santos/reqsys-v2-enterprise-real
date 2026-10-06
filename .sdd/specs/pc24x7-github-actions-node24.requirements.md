# PC24x7 — migração das GitHub Actions para Node.js 24

## Objetivo

Remover do workflow de bootstrap e reconciliação Teams no PC24x7 a dependência de Actions executadas em Node.js 20, mantendo a mesma semântica operacional e a pinagem imutável por SHA.

## Contexto evidenciado

- Workflow: `.github/workflows/pc24x7-teams-token-bootstrap.yml`.
- Runner físico: `DESKTOP-PDQK954`, GitHub Actions Runner `2.337.0`.
- O runner atende ao mínimo `2.327.1` exigido pelas versões oficiais baseadas em Node.js 24.
- As versões anteriores de `checkout`, `setup-python`, `azure/login` e `upload-artifact` emitiam aviso de descontinuação do Node.js 20.

## Requisitos

1. Todas as referências a Actions no workflow devem usar versões oficiais baseadas em Node.js 24.
2. Cada Action deve permanecer fixada pelo SHA completo e imutável da release aprovada.
3. A mudança não pode alterar triggers, permissões, environment, runner labels, parâmetros, segredos nem a ordem funcional dos jobs.
4. Um teste de regressão deve exigir os SHAs Node.js 24 aprovados e rejeitar os SHAs Node.js 20 substituídos.
5. Os contratos locais do workflow, do bootstrap do token e da governança do runner devem permanecer verdes.
6. A aceitação runtime exige execução real do workflow no PC24x7 após incorporação em `main`.
7. A execução de aceite deve concluir os jobs de reconcile e bootstrap sem aviso de Action baseada em Node.js 20.

## Critérios de aceite

- `tests/test_pc24x7_teams_token_bootstrap_workflow.py` aprovado, incluindo o teste de pinagem Node.js 24.
- `tests/test_bootstrap_pc24x7_teams_service_token.py` aprovado.
- `tests/test_self_hosted_runner_governance.py` aprovado.
- `scripts/validate_workflow_regression_contracts.py` aprovado.
- Workflow carregado como YAML válido.
- Execução física no runner PC24x7 concluída com sucesso e sem aviso de Node.js 20.
