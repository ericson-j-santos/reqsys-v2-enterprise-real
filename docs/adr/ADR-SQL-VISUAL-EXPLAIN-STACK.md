# ADR — SQL Visual Explain Stack

## Status

Consolidado como complemento offline da Query Intelligence Platform.

## Contexto

O ReqSys já possui análise SQL estática navegável em `/query-intelligence`. O PR #77 acrescenta valor quando é necessário gerar documentação versionável fora da interface.

## Decisão

Manter duas superfícies complementares:

1. **Query Intelligence** como experiência interativa canônica;
2. **SQL Visual Explain offline** como gerador de Markdown/Mermaid sem acesso a banco.

Ferramentas de banco continuam responsáveis por execução, `EXPLAIN` e `EXPLAIN ANALYZE`.

## Segurança

- nenhuma conexão de banco no script;
- nenhuma execução de SQL;
- comandos potencialmente destrutivos aparecem como alerta;
- exemplos não contêm credenciais nem dados reais;
- `EXPLAIN ANALYZE` não é automatizado neste incremento.

## Não adotado agora

SQLGlot continua como evolução possível, mas não é dependência necessária deste incremento.
