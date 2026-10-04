# Release Note — Governed Dev Auto Merge v0.1.0

## Resumo

Adiciona workflow manual para auto-merge governado exclusivamente para ambiente `dev`, com análise de risco, bloqueios de segurança e artifact de evidência.

## Entregas

- `.github/workflows/governed-dev-automerge.yml`
- `docs/ci/GOVERNED_DEV_AUTOMERGE.md`

## Decisão operacional

A automação fica limitada ao ambiente `dev`. Homologação e produção permanecem com promoção governada e aprovação humana explícita.

## Segurança

O workflow bloqueia auto-merge quando detectar alterações em áreas sensíveis como auth, security, secrets, cofre, JWT, CORS, deploy, infra, banco, homologação, produção e release.

## Status

Incremento inicial. Uso real com `dry_run=false` deve ocorrer somente após CI verde e validação do artifact de evidência.
