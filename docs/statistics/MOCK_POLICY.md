# Política de Mocks — Aba Estatísticas

## Regra principal

Mocks e dados locais são permitidos apenas para desenvolvimento, prototipação controlada e validação de layout. Eles nunca devem ser apresentados como dado real de produção.

## Classificação

| Tipo | Permitido | Condição |
|---|---|---|
| Mock interno local | Sim | Identificado como fonte local/dev |
| Mock externo | Somente como `nao_medido` | Não pode simular fonte real |
| Dado externo real | Sim | Exige fonte, coleta, TTL e confiabilidade |
| Estado avançado manual | Não | Exige evidência validada |

## Guard rail esperado para v2

Criar validação em CI para impedir deploy quando:

- `fonte.tipo === 'externa'` sem `ttlMinutos`;
- `fonte.origem` indicar mock e `estadoAtual !== 'nao_medido'`;
- `estadoAtual === 'avancado'` sem evidências suficientes;
- indicador sem fórmula estiver marcado como válido.
