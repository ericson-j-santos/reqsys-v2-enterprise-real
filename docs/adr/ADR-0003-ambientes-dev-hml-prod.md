# ADR-0003 — Ambientes Dev, Homologação e Produção

Status: aceito
Data: 2026-06-20

## Contexto

O ReqSys precisa separar desenvolvimento, homologação e produção para reduzir risco operacional, permitir testes reais e preservar governança.

## Decisão

Adotar separação explícita de ambientes:

| Ambiente | Uso | Regra |
| --- | --- | --- |
| `dev` | Desenvolvimento e testes locais/controlados | Permite mocks e dados fictícios. |
| `hml` | Homologação funcional, técnica e de integração | Deve simular produção sem expor dados sensíveis. |
| `prod` | Operação real | Exige CI verde, gates de segurança, auditoria e rollback. |

Toda alteração deve declarar o ambiente afetado.

## Consequências

- Reduz risco de aplicar mudanças diretamente em produção.
- Facilita validação progressiva.
- Permite rastrear defeitos por ambiente.

## Critérios de aceite

- Configuração parametrizada por ambiente.
- Segredos fora do repositório.
- Deploy produtivo condicionado aos gates definidos.
- Evidência de validação em homologação quando aplicável.
