# Modelo Operacional — Aba Estatísticas

## Objetivo operacional

Transformar a aba Estatísticas em uma área de decisão da própria solução, com visibilidade clara de estado atual, alvo, tendência, fontes e pendências.

## Papéis

| Papel | Responsabilidade |
|---|---|
| Usuário administrador | Avaliar indicadores, pendências e evolução da solução |
| Squad técnico | Corrigir lacunas, conectar fontes e manter testes |
| Governança | Validar fonte, fórmula, confiabilidade e uso de dados externos |
| CI/CD | Bloquear regressões, mocks indevidos e ausência de evidência |

## Ciclo operacional

1. Coletar dados internos.
2. Validar contrato do indicador.
3. Calcular estado atual.
4. Comparar com estado alvo.
5. Exibir pendências e evidências.
6. Permitir drill-down analítico.
7. Registrar evolução em changelog/release note.
8. Bloquear publicação quando guard rails falharem.

## Regras de uso de informação externa

- Toda fonte externa deve ter origem identificável.
- Toda fonte externa deve ter data de coleta.
- Toda fonte externa deve ter TTL.
- Toda fonte externa deve ter confiabilidade atribuída.
- Toda fonte externa deve ser claramente separada de dado interno.

## Critério de maturidade

A aba só pode ser considerada avançada quando os indicadores principais forem alimentados por fontes reais, os testes estiverem verdes e os guard rails estiverem bloqueando regressões em CI/CD.
