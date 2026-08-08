# Acompanhamento Teams da coleta governada

## Objetivo

Enviar mensagens de acompanhamento da coleta de requisitos sem criar uma segunda infraestrutura de mensageria ou observabilidade.

A fonte operacional continua sendo a fila central `teams_notification_queue`, já exposta no Control Center de notificações do ReqSys.

## Eventos

| Evento | Tipo | Quando ocorre |
|---|---|---|
| Coleta requer refinamento | `coleta_requisito_refinamento` | A avaliação ainda não atingiu o gate mínimo de geração |
| Requisito gerado | `coleta_requisito_gerado` | A coleta atingiu o gate e produziu ou reutilizou um requisito |

## Deduplicação

A chave de deduplicação é um SHA-256 calculado a partir de:

```text
coleta-requisitos:<hash da chave de idempotência>:<tipo do evento>
```

A mesma coleta não cria duas mensagens do mesmo tipo. Eventos diferentes da mesma coleta permanecem independentes.

## Rastreabilidade

A mensagem e a fila preservam o mesmo `correlation_id` da coleta. As tentativas de entrega do gateway acrescentam um sufixo interno de tentativa sem quebrar a correlação com o evento original.

## Segurança e minimização

As mensagens de acompanhamento não repetem o problema, objetivo, regras de negócio, critérios de aceite ou outros textos funcionais informados pelo solicitante.

A metadata persistida contém somente identificadores técnicos, hashes, pontuação, classificação, quantidade de pendências, origem e código do requisito quando existir. O sanitizador da fila central continua removendo chaves relacionadas a tokens, segredos, autorização e webhooks.

## Política de entrega

O primeiro incremento utiliza o canal operacional `webhook`, já governado pelo Teams Messaging Gateway.

- se o webhook estiver disponível, a fila tenta entregar imediatamente;
- se não estiver disponível, a mensagem permanece `PENDENTE` para processamento posterior;
- em `test`, `testing` e `ci`, envio externo é desabilitado;
- falha de mensageria não bloqueia a avaliação nem a geração do requisito;
- retentativas e DLQ continuam sob o Control Center existente.

## Monitoramento

O endpoint `GET /v1/dashboard/coleta-requisitos` passa a incluir `acompanhamento_teams`, derivado diretamente da fila central:

- notificações totais;
- pendentes;
- processando;
- enviadas;
- falhas;
- canceladas;
- taxa de sucesso;
- latência média;
- última entrega.

O `Painel do dia` mostra esses indicadores na seção de qualidade da coleta e oferece acesso direto a `/notificacoes` para investigação operacional.

## Critérios de aceite

1. A mesma coleta e o mesmo tipo de evento geram no máximo um item na fila central.
2. Refinamento e geração podem gerar eventos distintos para a mesma coleta.
3. Nenhum conteúdo funcional sensível é duplicado em metadata de acompanhamento.
4. Falha ou ausência do Teams não interrompe o fluxo principal de requisitos.
5. O Dashboard lê o estado de entrega da própria `teams_notification_queue`.
6. `correlation_id` permanece rastreável entre coleta, fila e gateway.
