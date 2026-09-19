# PC24x7 Runner Recovery e Teams Bot DEV — requisitos

## Objetivo

Consolidar a recuperação do GitHub Actions Runner no DESKTOP-PDQK954 e a materialização governada do Teams Bot em DEV, sem criar runtime paralelo, sem expor segredos e sem tocar HML/STG/PROD.

## Critérios de aceite

1. A recuperação do runner deve detectar processo, serviço, tarefa agendada ou instalação local existente antes de tentar iniciar qualquer alvo.
2. Ausência ou ambiguidade de alvo deve falhar fechada com motivo objetivo.
3. O provisionamento Teams Bot deve aceitar somente ambiente DEV e a confirmação explícita prevista pelo script.
4. A credencial existente do Bot deve ser lida do Key Vault sem aparecer em evidência; após a recriação do runtime, o segredo não deve ser propagado ao subprocesso de E2E.
5. O runtime alvo deve ser vinculado ao SHA exato informado.
6. A evidência deve registrar `production_touched=false` e `secret_value_exposed=false`.
7. Testes positivos e negativos devem cobrir recuperação do runner e guardrails do Teams Bot.
8. Nenhuma promoção HML/STG/PROD ou merge é parte deste incremento.

## Rastreabilidade

- #1770 — separação Builder/Validator/E2E.
- #1532 — Central de Conversas IA via Teams em DEV.
- #993 — backlog operacional consolidado.
- #1705 — ações autorizadas do ReqSys.
