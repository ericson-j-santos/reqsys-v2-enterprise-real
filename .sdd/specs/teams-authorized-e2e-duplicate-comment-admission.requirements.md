# Admissão idempotente dos comandos Teams E2E DEV

## Problema observado
Dois comentários autorizados distintos na issue #1705, separados por poucos segundos,
originaram dois gateways e dois E2Es físicos no mesmo SHA (runs 37950807854 e
37950812177), embora a concorrência por comment.id tenha operado corretamente.
O gate não deve cancelar comentários distintos e não deve usar o texto do comentário
como concurrency group, conforme regra anterior.

## Critérios de aceite
1. Somente o comando exato `/reqsys run pc24x7-teams-e2e-dev` recebe a
   admissão contra duplicatas; demais comandos preservam o comportamento vigente.
2. Dois comentários idênticos criados dentro de 120 segundos: o comentário de
   menor ID (anterior e autorizado) permanece admitido, e o posterior não dispara
   outro workflow, mesmo se os gateways executarem em ordem invertida.
3. A verificação usa comentários completos de #1705, faz readback obrigatório do
   próprio comment.id/timestamp e falha fechado se a API estiver indisponível,
   truncada ou inconsistir; não confiar em cache ou checks antigos.
4. Comentário autorizado repetido após o intervalo pode ser admitido
   novamente; o intervalo é um cooldown e não uma proibição permanente.
5. A concorrência por ID imutável e `cancel-in-progress: false` permanecem
   inalterados. Nenhum run físico deve ser cancelado pelo controle de duplicidade.
6. A duplicata suprimida é registrada em artifact sanitizado com ID do
   comentário canônico, SHA esperado e status `duplicate_suppressed`;
   não registrar conteúdo dos comentários, tokens nem IDs privados do Teams.
7. Validar casos positivos, duplicação, ordem invertida, cooldown,
   entrada não autorizada e API/readback incompleto, além de executar
   os gates da PR no SHA exato.
8. A medida previne duplo despacho por dois comentários próximos. Não substitui
   o replay real do mesmo `activity.id` no webhook nem prova a idempotência
   de mensagens Teams; esta permanece requisito separado da issue #1532.

## Segurança e limite
Somente DEV. Sem segredos, deploy, promoção, produção, força de push ou
alterações em branch protegida. O checkout usa SHA exato da main e credenciais
persistentes desativadas.
