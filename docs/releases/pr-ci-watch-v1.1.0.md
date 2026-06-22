# Release Note — PR CI Watch v1.1.0

## Resumo

Evolui o PR CI Watch para P1 com classificação de falhas baseada em workflows, jobs e steps falhos retornados pela API do GitHub Actions.

## Entregas

- Consulta de jobs associados a workflow runs `unhealthy`.
- Identificação de steps falhos.
- Classificação de causa provável.
- Ação recomendada por categoria de falha.
- Artifact `pr-ci-watch-report` enriquecido com `failed_jobs`.
- Runbook atualizado para P1.

## Categorias de falha

- `conflito_de_merge`
- `gate_de_governanca`
- `qualidade_estatica`
- `teste_automatizado`
- `artifact_ausente_ou_invalido`
- `branch_protection`
- `runtime_ou_deploy`
- `falha_nao_classificada`

## Segurança

- Não faz merge automático.
- Não altera produção.
- Não altera draft automaticamente.
- Não baixa logs completos no P1.
- Usa metadados de jobs e steps, reduzindo risco de exposição de secrets.

## Próximo incremento

Baixar logs resumidos de jobs falhos com mascaramento e criar comentário único atualizável no PR.
