# Requisitos — descrição Redmine CRLF

A correção da divergência reproduzida na issue #1686 foi solicitada pelo
proprietário. Escopo: recuperar a sincronização sem relaxar a releitura e
sem alterar o conteúdo canônico do requisito.

## Critérios de aceite

1. Canonicalizar apenas CRLF/LF/CR da descrição enviada, conforme o setter
   oficial do Redmine 6.1.5; preservar título, espaços, tabs e linhas vazias.
2. Confirmar atualização por GET independente e igualdade exata. Mudanças
   reais de conteúdo, título, espaço ou linha vazia continuam sendo rejeitadas.
3. Repetir a sincronização sem novo PUT, evento ou checkpoint desnecessário.
4. Testes do serializador e ORM não devem inicializar a API/OAuth na coleta;
   testes que pedem o cliente HTTP continuam carregando a aplicação real.
5. Executar regressão positiva/negativa, replay e E2E real no SHA final.
6. Manter auditoria do bundle e gates de PR. E2E isolado não autoriza deploy
   nem equivale a recuperação Render/PC24x7 ou projeção do TODO Global.

Origem técnica: https://github.com/redmine/redmine/blob/6.1.5/app/models/issue.rb
