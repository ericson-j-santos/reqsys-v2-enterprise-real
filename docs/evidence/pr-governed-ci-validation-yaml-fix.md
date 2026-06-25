# Evidence — PR Governed CI Validation YAML Fix

## Contexto

O PR #257 apresentou falha no workflow `PR Governed CI Validation`, passo `Validar sintaxe YAML dos workflows`.

## Correção

- A validação YAML passou a usar parser disponível no runner (`Ruby YAML`) em vez de depender implicitamente de pacote Python externo.
- O workflow cria diretório de evidência antes das validações.
- As etapas de evidência e upload usam `if: always()` para publicar artifact mesmo quando uma validação falhar.

## Guardrails

- Sem deploy.
- Sem alteração produtiva.
- Sem alteração de secrets.
- Sem mudança de permissões.
- Sem merge automático.

## Evidência esperada

- `PR Governed CI Validation` verde.
- Artifact `pr-governed-ci-validation-<pr>` publicado.
