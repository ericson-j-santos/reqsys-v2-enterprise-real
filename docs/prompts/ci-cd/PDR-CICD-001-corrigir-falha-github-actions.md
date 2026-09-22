# PDR-CICD-001 — Corrigir falha de GitHub Actions

Versão: 1.0.0  
Status: active  
Risco padrão: high

## Objetivo

Corrigir falhas de CI pela menor causa raiz possível, sem mascarar erro ou reduzir gates.

## Execução

1. Ler job, step e log da tentativa mais recente.
2. Separar falha determinística de instabilidade externa.
3. Identificar causa raiz e impacto em outros workflows.
4. Aplicar correção mínima e reutilizável.
5. Validar localmente quando possível.
6. Executar rerun e confirmar conclusão verde.

## Guardrails

Não usar `continue-on-error`, exclusões amplas ou redução de cobertura para esconder falhas.

## Saída obrigatória

Log, causa raiz, patch, validação, rerun, link do workflow e estado final.
