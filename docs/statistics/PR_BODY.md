## Resumo

Implementa a primeira versão funcional da aba `/estatisticas` no ReqSys para uso próprio da solução, com estatísticas internas evidenciadas e preparação governada para informações externas auditáveis.

## Entregas principais

- Rota `/estatisticas` registrada no Vue Router.
- Item `Estatísticas` adicionado ao menu principal.
- Nova tela `EstatisticasView.vue` com:
  - cards executivos;
  - filtros;
  - cards analíticos;
  - tabela consolidada;
  - evidências e pendências por indicador.
- Novo serviço `estatisticas.js` com:
  - contrato de indicadores;
  - fontes internas/externas;
  - cálculo de resumo;
  - validação de guard rails.
- Testes unitários para impedir:
  - indicador sem fonte;
  - indicador sem fórmula;
  - estado avançado sem evidência.
- Documentação governada em `docs/statistics/`.

## Governança aplicada

- Estado atual evidenciado separado de estado alvo.
- Dado externo inicial mantido como `nao_medido`.
- Fonte externa exige TTL.
- Indicador sem fonte/fórmula é inválido.
- PR deve permanecer em draft até CI verde.

## Validação

- Comparação com `main`: branch à frente e sem atraso antes da abertura do PR.
- Testes/build dependem do GitHub Actions após abertura do PR.

## Próximo incremento

Conectar dados reais internos via backend antes de expandir fontes externas.
