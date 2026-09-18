# Status público — GitHub → Microsoft Teams

[![Teams Public Dashboard Smoke](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/workflows/teams-public-dashboard-smoke.yml/badge.svg?branch=main)](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/workflows/teams-public-dashboard-smoke.yml)

## Evidências navegáveis

- [Dashboard público](https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/)
- [Dados de SLO](https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/data.json)
- [Status da certificação](https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/certification-status.json)
- [Workflow de smoke público](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/workflows/teams-public-dashboard-smoke.yml)
- [Workflow de publicação do dashboard](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/workflows/teams-notification-dashboard.yml)
- [Issues de status operacional](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues?q=is%3Aissue+%22%5BSTATUS%5D%5BTEAMS%5D%22)

## Contrato do badge

O badge representa a última execução do workflow `Teams Public Dashboard Smoke` na branch `main`.

O workflow só conclui verde quando:

1. o dashboard responde HTTP 200;
2. os marcadores funcionais estão presentes no HTML;
3. `data.json` atende ao contrato público;
4. `certification-status.json` atende ao contrato da certificação;
5. os dados publicados não estão vencidos;
6. nenhum endpoint depende de credenciais para leitura.

O badge comprova disponibilidade técnica da evidência pública. Ele não substitui os estados `provisional_gold` e `gold_certified`, que continuam dependentes das amostras, do SLO e das janelas temporais definidas.
