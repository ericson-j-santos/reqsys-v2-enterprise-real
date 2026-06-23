# Workflow Auto Remediation

## Objetivo
Executar rerun seguro apenas para falhas transitórias.

## Permitido
- timeout transitório
- network flakes
- runner unavailable
- cancel transient

## Bloqueado
- secrets
- permissions
- branch protection
- merge conflict
- deploy produção

## Evidências
Artifact: workflow-runtime-health
