# Kubernetes DEV — environment-observability-api build-only

## Objetivo

Desacoplar a publicação da imagem GHCR do deploy Fly para permitir que Kubernetes DEV consuma uma imagem imutável sem tocar runtime Fly.

## Requisitos

1. Reutilizar o workflow existente `.github/workflows/environment-observability-promotion.yml`.
2. Adicionar entrada booleana `build_only`, default `false`, preservando o comportamento existente.
3. Em `build_only=true`, executar validação, testes, build/push GHCR, SBOM/provenance e artifact de build.
4. Em `build_only=true`, todos os jobs de deploy Fly DEV/STG/PROD devem ficar skipped.
5. O artifact deve registrar commit, image, digest, workflow_run_id e build_only.
6. O Authorized Actions Gateway deve aceitar somente `/reqsys run environment-observability-build-only-dev` na issue #1705.
7. A rota deve fixar `main`, `promote_to=development` e `build_only=true`; não aceitar parâmetros arbitrários.
8. A rota deve permanecer em runner GitHub-hosted e fora do watchdog self-hosted.
9. Nenhum segredo deve ser emitido em evidência.
10. Este incremento não cria Deployment Kubernetes ainda; ele produz o digest real que alimentará a próxima fatia.

## Critérios de aceite

- testes contratuais positivos/negativos verdes;
- Pre-PR Readiness verde no HEAD exato e behind_by=0;
- PR com gates completos verdes;
- após merge, gateway despacha o workflow no SHA corrente de main;
- job `Validate and publish immutable image` termina success;
- `Deploy development`, `Promote to staging` e `Promote to production` terminam skipped;
- artifact `environment-observability-build-evidence` contém digest `sha256:` não vazio vinculado ao SHA pós-merge.
