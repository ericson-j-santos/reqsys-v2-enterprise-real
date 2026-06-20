# Analytics e Drill-Down — Padrão Ouro

## Objetivo

Garantir que informações relevantes sejam navegáveis, explicáveis e acionáveis.

## Fluxo obrigatório

```text
Indicador → gráfico → analítico filtrado → detalhe → ação operacional
```

## Regras

- Todo dashboard crítico deve permitir navegação para detalhe.
- Filtros devem ser persistidos entre telas.
- Cards devem abrir o analítico correspondente já filtrado.
- Analytics deve respeitar permissões e ambiente.
- Exportação deve preservar rastreabilidade.

## Capacidades recomendadas

- drill-down;
- drill-through;
- exportação;
- filtros dinâmicos;
- deep-link;
- histórico;
- auditoria;
- reprocessamento operacional.

## Exemplo

```text
Card: Integrações com erro
→ Clique
→ Lista filtrada status=erro
→ Clique no item
→ Log correlacionado
→ Reprocessar integração
```

## Integração com arquitetura viva

Os analytics devem permitir:

- navegar para fluxo;
- abrir ADR relacionado;
- abrir documentação;
- abrir pipeline;
- abrir logs correlacionados.
