# GitLab Environments e Review Apps Baseline

## Objetivo

Definir a baseline de ambientes da ReqSys v2 Enterprise GitLab Edition para suportar operação governada com GitLab Environments e Review Apps.

## Ambientes previstos

| Ambiente | Tipo | Aprovação | Uso |
|---|---|---|---|
| `development` | persistente | automática/controlada | integração técnica |
| `staging` | persistente | manual | validação pré-produção |
| `production` | protegido | coordenadora obrigatória | runtime público controlado |
| `review/*` | efêmero | desativado | reservado para futuro runtime substituto |

## Variáveis esperadas

| Variável | Finalidade |
|---|---|
| `REQSYS_DEV_URL` | URL ambiente development |
| `REQSYS_STAGING_URL` | URL ambiente staging |
| `REQSYS_PRODUCTION_URL` | URL pública produção |
| `REQSYS_REVIEW_BASE_URL` | base para Review Apps |

## Regras de governança

- Produção deve ser protegida e exigir aprovação manual.
- Review Apps permanecem desativados até aprovação do runtime substituto.
- URLs reais devem vir de GitLab CI/CD Variables.
- Rollback deve estar documentado antes de ativar deploy real.
- Deploy real deve publicar artifacts de evidência.
- Fly.io é proibido como destino, fallback ou contingência.

## Escopo deste incremento

Este baseline é exclusivamente report-only. `gitlab/ci/environments.yml` não possui jobs de deploy ou de Review App.

## Próximos passos

1. Aprovar o runtime substituto e sua estratégia de release.
2. Proteger o environment `production`.
3. Definir variáveis e URLs sem dependências do provedor retirado.
4. Implementar deploy e Review Apps somente após validação do substituto.
5. Adicionar rollback governado antes da ativação.
