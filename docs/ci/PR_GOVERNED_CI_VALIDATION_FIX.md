# Correção — PR Governed CI Validation

## Problema

O workflow `PR Governed CI Validation` executa validação de sintaxe YAML com Python usando `import yaml`, mas não instalava explicitamente o pacote `PyYAML` antes da execução.

## Correção

Adicionada etapa determinística antes da validação YAML:

```bash
python -m pip install --upgrade pip
python -m pip install "PyYAML==6.0.2"
```

## Impacto

- Reduz falha recorrente em PRs recentes.
- Mantém validação YAML existente.
- Não altera runtime, deploy, frontend ou backend.
- Mantém artifact `pr-governed-ci-validation-*`.

## Validação esperada

- `PR Governed CI Validation` verde.
- Artifact de evidência publicado.
- PRs draft recentes deixam de herdar bloqueio por dependência ausente.
