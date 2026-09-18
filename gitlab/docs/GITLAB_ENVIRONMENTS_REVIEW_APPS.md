# GitLab Environments e Review Apps Baseline

## Objetivo

Definir a baseline de ambientes da ReqSys v2 Enterprise GitLab Edition para suportar operação governada com GitLab Environments e Review Apps.

## Ambientes previstos

| Ambiente | Tipo | Aprovação | Uso |
|---|---|---|---|
| `development` | persistente | automática/controlada | integração técnica |
| `staging` | persistente | manual | validação pré-produção |
| `production` | protegido | coordenadora obrigatória | runtime público controlado |
| `review/*` | efêmero | manual placeholder | validação isolada por Merge Request |

## Variáveis esperadas

| Variável | Finalidade |
|---|---|
| `REQSYS_DEV_URL` | URL ambiente development |
| `REQSYS_STAGING_URL` | URL ambiente staging |
| `REQSYS_PRODUCTION_URL` | URL pública produção |
| `REQSYS_REVIEW_BASE_URL` | base para Review Apps |

## Regras de governança

- Produção deve ser protegida e exigir aprovação manual.
- Review Apps devem ser efêmeros e possuir auto stop.
- URLs reais devem vir de GitLab CI/CD Variables.
- Rollback deve estar documentado antes de ativar deploy real.
- Deploy real deve publicar artifacts de evidência.

## Escopo deste incremento

Este incremento não executa deploy real. Ele cria a estrutura governada para habilitar ambientes quando houver GitLab Runner, variáveis, registry e estratégia de release configurados.

## Próximos passos

1. Configurar variáveis de ambiente no GitLab.
2. Proteger environment `production`.
3. Implementar deploy real em `staging`.
4. Implementar Review Apps com URL real.
5. Adicionar rollback governado.
