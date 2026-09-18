# PR Summary — Aba Estatísticas v1

## Resumo

Implementa a primeira versão funcional da aba `/estatisticas` no ReqSys, com foco em estatísticas internas evidenciadas e preparação governada para uso de informações externas auditáveis.

## Entregas

- Nova rota `/estatisticas`.
- Novo item `Estatísticas` no menu principal.
- Nova tela Vue com cards executivos, filtros, cards analíticos e tabela consolidada.
- Serviço frontend com contrato de indicadores, fontes, fórmulas, confiabilidade, evidências e pendências.
- Testes unitários de guard rails.
- Documentação de implementação, checklist, release note, validação inicial e próximo incremento.

## Governança

- Não promove estado atual para avançado sem evidência.
- Dado externo inicial permanece como `nao_medido`.
- Indicador sem fonte/fórmula é bloqueado pelo validador.
- Mock externo não é tratado como dado real.

## Validação

Validação estrutural realizada por inspeção e comparação GitHub. Testes/build pendentes de execução pelo CI do PR.

## Próximo incremento

Conectar indicadores reais internos via backend antes de expandir fontes externas.
