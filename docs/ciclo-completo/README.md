# ReqSys — Painel Central de Andamentos

## Objetivo

Centralizar o acompanhamento operacional sem manter andamento manual congelado no
repositório. O painel é uma **projeção**: as fontes oficiais continuam sendo
GitHub/Actions, TODO Global, evidências do Microsoft Teams e evidências do Runtime
PC24x7.

## Estado e atualização

O HTML versionado em `docs/painel-ciclo-completo-reqsys.html` não contém mais
PRs, percentuais ou decisões operacionais embutidas.

O workflow `Teams Notification Dashboard` preserva o contrato Teams existente e,
no mesmo run, gera `global-status.json` com:

- SHA atual e PRs abertos do ReqSys;
- último CI observado por repositório;
- saúde da reconciliação do TODO Global, explicitamente como projeção;
- certificação/SLO do Microsoft Teams;
- evidências dos workflows Runtime PC24x7;
- estado dos repositórios operacionais configurados, incluindo Power BI,
  e-mail, Portal, Noteri, Worker Pool, observabilidade e E2E.

A coleta roda a cada hora e também quando mudanças relevantes chegam à `main`.
Uma fonte privada ou temporariamente inacessível é marcada `unavailable`; o
painel nunca converte ausência de evidência em sucesso.

## Fontes e contratos

| Arquivo | Finalidade |
|---|---|
| `config/operational-dashboard-projects.json` | Lista versionada das frentes/repositórios que devem aparecer. |
| `scripts/generate_cycle_dashboard_state.py` | Coletor somente leitura da API GitHub e compositor do estado vivo. |
| `docs/painel-ciclo-completo-reqsys.html` | Interface do painel central; consome `global-status.json`. |
| `docs/ciclo-completo/estado-ciclo-reqsys.json` | Bootstrap não operacional; nunca contém andamento congelado. |
| `scripts/validar_painel_ciclo.py` | Gate contra regressão para estado estático, dependências externas e segredos. |
| `.github/workflows/teams-notification-dashboard.yml` | Produtor de Teams + estado global, mantendo compatibilidade. |
| `.github/workflows/deploy-reqsys-pages-composite.yml` | Empacotador/publicador canônico do Pages, sujeito ao gate explícito existente. |

## Microsoft Teams

O painel detalhado do Teams é preservado em `/teams/`. O painel central exibe
somente o resumo da mesma evidência de certificação; não recalcula o SLO nem
declara entrega real sem o contrato produzido pelo workflow Teams.

## TODO Global

O TODO Global continua sendo a fonte canônica. O painel mostra somente a saúde do
workflow de reconciliação/projeção. Não usa issue, planilha ou dashboard como
substituto da fonte canônica.

## Runtime PC24x7

Runs de workflow são exibidos como evidência de automação. Quando um critério
exige pickup físico, health/build-info same-SHA ou efeito externo, um run verde
isolado não é promovido a sucesso físico.

## Validação local

```bash
python -m pytest tests/test_generate_cycle_dashboard_state.py tests/test_validar_painel_ciclo.py -q
python scripts/validar_painel_ciclo.py
```

O E2E real do incremento ocorre após integração, quando uma nova execução do
produtor gera `global-status.json` no SHA corrente. Publicar essa saída no
GitHub Pages continua sendo uma ação separada e governada; alterar o código não
dispara deploy automaticamente.
