# Checklist — PR Quality Review

| Critério | Resultado esperado |
|---|---|
| Sem dependência do CodeRabbit | `.coderabbit.yaml` apenas documental |
| Workflow próprio | `.github/workflows/pr-quality-review.yml` presente |
| Script determinístico | `scripts/pr_quality_review.py` presente |
| Artifact | `pr-quality-review-report` publicado |
| Critical | Bloqueia workflow |
| Warning | Visível sem bloqueio padrão |
| Evidência | JSON e Markdown gerados |
