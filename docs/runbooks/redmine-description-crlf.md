# ReqSys ↔ Redmine: descrição e CRLF

Referência: #1686 / TODO-7. Incremento de correção, sem deploy.

## Causa e menor correção

O build real do Redmine 6.1.5.stable, run 39136708299/job 117702595095
no repositório redmine, interrompeu a sincronização: descrição esperada com
194 caracteres, retornada com 204; título correspondente.

O setter `Issue#description=` da tag 6.1.5 normaliza CRLF, LF e CR para CRLF.
O adapter ReqSys emitia dez quebras LF no cenário reproduzido. A aplicação
do mesmo contrato ao texto de teste reproduziu exatamente os comprimentos
194/204. A serialização agora canonicaliza apenas as quebras da descrição
para CRLF antes do envio; título, espaços, tabulações, linhas vazias e demais
caracteres permanecem preservados. O requisito armazenado não é modificado.

A comparação literal do reconciliador e a releitura independente permanecem
inalteradas. Não usar strip, comparação aproximada ou remoção de espaços.

Fonte: https://github.com/redmine/redmine/blob/6.1.5/app/models/issue.rb

## Aceite e prevenção

- Payload idempotente para LF, CRLF, CR e formas mistas; preservar conteúdo.
- Reconciliador deve aceitar persistência CRLF e repetir sem novo PUT,
  checkpoint ou evento de auditoria por diferença apenas de representação.
- Releitura deve continuar rejeitando mudança de título, conteúdo, espaços
  ou remoção de linha vazia; falha não deve produzir checkpoint de sucesso.
- Executar o E2E real no SHA corrigido, com ida/volta, releitura, replay e
  falha/quarentena. Servidor simulado de teste não prova esse aceite externo.

Foram preparados 17 casos de regressão: 12 do serializador, um de sincronização
com replay e quatro controles de divergência. Na validação prévia isolada,
12 casos puros passaram; todos os 12 falharam com o serializador anterior.
Após restaurar a correção, os 12 passaram novamente. Sintaxe Python validada.
Essa validação em memória não equivale ao pytest completo do backend ou E2E.
Os resultados do CI e do runtime devem ser vinculados ao HEAD publicado.

## Escopo e rollback

Não altera transporte, permissões, propriedade dos campos, banco ou versão
Redmine. Não corrige as vulnerabilidades de mail/rubyzip/sqlite3 encontradas
na auditoria do bundle; essa pendência continua bloqueando publicação.
Reverter o commit restaura o comportamento anterior, inclusive o falso
negativo do readback. Nenhum rollback autoriza bypass de segurança.
