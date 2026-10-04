# Reconciliação do PR #2222 — runtime DEV portátil

A branch foi sincronizada com a `main` atual sem reescrever os 34 arquivos do incremento.

## Prova de integração segura

- merge-base observado: `8a7043a2accaa2117fbe8d97f59891cf252c2a2c`;
- commits novos na `main`: 11;
- arquivos alterados na `main` desde o merge-base: 108;
- arquivos alterados pelo PR: 34;
- interseção de caminhos: **0**.

Como não existe sobreposição de caminhos, a reconciliação usa a árvore da `main` vigente e reaplica exatamente os blobs do HEAD do PR, preservando modos e conteúdo.

## Escopo operacional

Este commit apenas sincroniza Git. Não restaura banco, não movimenta chaves, não publica rota, não executa deploy e não altera runtime local.

Os bloqueios operacionais descritos no PR continuam dependentes de evidência própria e não são considerados resolvidos por esta sincronização.

## Critério de integração

- `behind_by=0`;
- nenhum conflito;
- gates obrigatórios verdes no HEAD reconciliado;
- nenhuma evidência operacional antiga usada como autorização de promoção.
