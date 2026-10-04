# Teams ReqSys Logs v1.1.0

## Correção

O envio anterior utilizava texto simples dentro de um único bloco do cartão do Power Automate. No Teams mobile, as quebras de linha eram eliminadas e os campos apareciam concatenados.

## Implementação

- adiciona Adaptive Card 1.2 estruturado;
- separa cabeçalho, resumo, fatos e falhas;
- adiciona botão para abrir a execução no GitHub;
- limita a oito falhas visíveis e informa a quantidade adicional;
- envia `adaptiveCard` e `adaptiveCardJson` ao webhook validado;
- reutiliza `TEAMS_WEBHOOK_URL` e `TEAMS_WEBHOOK_RECIPIENT`;
- mantém o Teams Messaging Gateway como fallback;
- registra somente hashes e metadados no artifact de evidência.

## Validação

- compilação Python;
- nove testes unitários;
- validação do contrato do cartão;
- validação do limite visual;
- validação de URL do GitHub;
- dry-run do webhook adaptável;
- validação de evidência sem corpo do cartão.

## Rollback

Reverter esta versão restaura o envio em texto simples pelo gateway. Nenhuma migração de banco ou alteração de ambiente é necessária.

`production_touched=false`
