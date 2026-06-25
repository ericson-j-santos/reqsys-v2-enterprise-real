# Padrão de E-mail — Relatório Operacional Visual v1

## Decisão

Todo relatório operacional enviado por e-mail deve usar formato executivo visual, com leitura rápida, status semafórico, cards de KPI, alertas priorizados e rodapé técnico rastreável.

## Objetivo

Substituir e-mails tabulares extensos por um dashboard executivo por e-mail, compatível com Outlook, Gmail e clientes mobile.

## Regras obrigatórias

- HTML autocontido com CSS inline.
- Sem JavaScript.
- Sem CDN.
- Sem Canvas.
- Sem dependência externa para renderização.
- Escapar todo conteúdo dinâmico.
- Incluir `correlation_id`, ambiente, versão e data/hora de geração.
- Exibir status geral no topo.
- Usar cards para KPIs principais.
- Exibir alertas priorizados antes dos detalhes.
- Usar tabelas apenas para Top N ou detalhamento realmente necessário.

## Semáforo operacional

| Status | Uso |
|---|---|
| NORMAL | Operação saudável |
| ATENCAO | Degradação, risco ou SLA próximo do limite |
| CRITICO | Falha, indisponibilidade ou SLA violado |
| INFORMATIVO | Informação neutra |
| PROCESSANDO | Execução em andamento |

## Estrutura canônica

1. Cabeçalho executivo
2. Status geral
3. Resumo executivo
4. Cards de KPIs
5. Alertas prioritários
6. Indicadores por processo
7. Rodapé técnico rastreável

## Implementação

Arquivo principal:

```text
backend/app/services/email_report_template.py
```

Teste:

```text
backend/tests/test_email_report_template.py
```

## Uso esperado

O serviço de envio atual deve chamar `renderizar_relatorio_email(relatorio)` e usar o HTML retornado como corpo do e-mail.

## Critérios de aceite

- O relatório destaca criticidade em menos de 30 segundos de leitura.
- O HTML não contém `<script>`.
- O conteúdo dinâmico é escapado.
- O e-mail contém rastreabilidade operacional.
- O layout permanece legível em mobile.
- As informações críticas aparecem antes das tabelas.
