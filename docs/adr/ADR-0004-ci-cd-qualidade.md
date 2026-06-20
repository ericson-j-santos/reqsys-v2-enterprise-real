# ADR-0004 — CI/CD, Qualidade e Política de Merge

Status: aceito
Data: 2026-06-20

## Contexto

O ReqSys possui múltiplas frentes e PRs concorrentes. A ausência de validação completa antes do merge aumenta o risco de regressão.

## Decisão

Nenhum merge em `main` deve ocorrer antes do CI concluir com sucesso, salvo exceção formal, justificada e documentada.

Gates mínimos recomendados:

- Lint e análise estática.
- Testes automatizados relevantes por stack.
- Build de frontend/backend quando aplicável.
- Auditoria de dependências.
- Validação responsiva para telas críticas.
- Evidência de teste no PR.

## Consequências

- A velocidade de merge fica condicionada à confiabilidade do pipeline.
- PRs antigos devem ser revalidados contra a `main` atual.
- PRs duplicados devem ser consolidados ou encerrados com justificativa.

## Critérios de aceite

- PR não está em draft.
- Branch está mergeável.
- CI completo e verde.
- Escopo e rollback documentados.
- Sem alterações fora do objetivo declarado.
