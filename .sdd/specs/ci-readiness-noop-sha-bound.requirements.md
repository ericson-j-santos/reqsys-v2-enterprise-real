# Contrato de prontidão sem alterações e com SHA protegido

## Problema
A main do ReqSys executa dois critérios incompatíveis para PR sem diff. O Pre-PR classifica qualquer HEAD atualizado sem arquivos alterados como `not_applicable` mesmo quando o commit é diferente da base. O Admission Controller rejeita corretamente esse caso por não ter SHA idêntico. A PR #3120 expõe o defeito, e a mudança Teams já consta na main.

## Critérios de aceite
1. Apenas HEAD SHA idêntico à base, `behind_by=0` e lista de alterações vazia permitem `not_applicable`.
2. HEAD diferente sem diff jamais recebe `passed` ou `not_applicable`; deve permanecer `blocked` pela ausência de alteração material.
3. Branch atrasada e diff não vazio mantêm validação normal, sem contorno de regras de admissão.
4. `scripts/ci_admission_manifest.py` permanece estrito e não aceita evidência de outro SHA nem invariantes ausentes.
5. Testes positivos e negativos em `tests/test_pre_pr_readiness.py` e `tests/test_ci_admission_control.py` demonstram o caso antigo e a correção.
6. READY_FOR_PR precisa terminar `passed` no SHA atual, com artefato da execução e análise independente, antes de criar nova PR.
7. Não editar a PR #3120 para fabricar diff, não fazer merge/deploy por inferência, manter custo adicional R$ 0,00.

## Escopo
Alteração isolada do Pre-PR e testes, vinculada à issue #2117. Inclui adicionalmente uma correção pontual de segurança no lockfile do frontend, necessária para o gate existente de npm audit. Não altera código de interface, fluxo Teams, runtime nem políticas de proteção de branch.

## Evidência inicial
GitHub Actions #41376525482 registrou 92 testes direcionados aprovados e bloqueou `sdd:contract` por ausência de especificação. Este documento satisfaz a rastreabilidade exigida; a execução CI no SHA posterior e o E2E/controle negativo continuam necessários.

## Desbloqueio de segurança detectado no CI da PR #3125

O CI #41377203586 identificou em `frontend/package-lock.json` a dependência transitiva `follow-redirects@1.16.1` (via `axios`), afetada por GHSA-mrwp-f3q8-3g9p e reprovada por `npm audit --audit-level=high`. O contrato `axios -> follow-redirects ^1.16.0` aceita o patch 1.16.2. Foi proposta atualização somente de version/resolved/integrity no lockfile, com SRI de 1.16.2 verificável por `npm ci` no runner. Não reduzir a severidade exigida no gate nem fazer `npm audit fix` irrestrito.

### Aceite adicional
- `npm ci` verifica integridade do pacote atualizado, `npm audit --audit-level=high` passa, e o build do frontend conclui sem fallback.
- Permanecem as 4 vulnerabilidades moderadas, a serem tratadas separadamente conforme risco; não ocultar relatórios.
- Se o frontend precisar de Node atualizado, corrigir somente o runtime do job após prova no CI, preservando a versão mínima aceita pela ferramenta e os testes existentes.
- Como o lockfile faz parte do frontend, verificar os testes/E2E aplicáveis no SHA final antes de integrar. Nenhum deploy/merge nesta correção.
