# Guardrails — Monitorador de APIs Python Coverage Fix

## Permitido

- Aumentar cobertura por testes unitários/API.
- Mockar chamadas externas.
- Registrar evidência técnica e changelog.

## Bloqueado

- Reduzir o limiar `--cov-fail-under=85` sem evidência forte.
- Fazer deploy automático.
- Realizar chamadas externas reais no CI.
- Alterar secrets, permissões ou branch protection.

## Validação esperada

- Workflow `Testes Monitorador APIs Python` verde no PR.
- Etapa `Executar testes com cobertura mínima` concluída com sucesso.
