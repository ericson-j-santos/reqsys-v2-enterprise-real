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

## Nota operacional
Este PR permanece em draft e deve ser reavaliado após a estabilização dos incrementos governados já mergeados na `main`. O commit atual força nova evidência de CI e novo cálculo do `PR Conflict Guard`, sem executar merge, deploy ou remediação real.
