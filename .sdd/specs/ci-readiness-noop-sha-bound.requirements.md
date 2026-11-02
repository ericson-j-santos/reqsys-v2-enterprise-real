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
Alteração isolada do Pre-PR e testes, vinculada à issue #2117. Este incremento não altera entrega Teams, frontend, runtime ou políticas de proteção de branch.

## Evidência inicial
GitHub Actions #41376525482 registrou 92 testes direcionados aprovados e bloqueou `sdd:contract` por ausência de especificação. Este documento satisfaz a rastreabilidade exigida; a execução CI no SHA posterior e o E2E/controle negativo continuam necessários.
