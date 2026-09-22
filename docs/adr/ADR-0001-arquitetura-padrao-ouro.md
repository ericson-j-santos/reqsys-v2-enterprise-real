# ADR-0001 — Arquitetura Padrão Ouro do ReqSys

Status: aceito
Data: 2026-06-20

## Contexto

O ReqSys precisa evoluir de forma corporativa, rastreável e segura, suportando requisitos, IA, integrações, painéis, automações, CI/CD e governança.

## Decisão

Adotar arquitetura modular e evolutiva, com separação clara entre apresentação, API/BFF, aplicação, domínio, portas/adaptadores, infraestrutura e observabilidade.

Quando houver domínio relevante, múltiplas integrações ou necessidade de testes isolados, a referência passa a ser arquitetura hexagonal.

## Consequências

- Menor acoplamento entre frontend, backend e integrações.
- Testes mais simples por camada.
- Maior capacidade de substituir conectores e provedores.
- Documentação por ADR passa a ser obrigatória para decisões transversais.

## Critérios de aceite

- Código organizado por responsabilidade.
- Integrações encapsuladas em adaptadores.
- Regras de negócio fora de controllers/componentes visuais.
- Testes cobrindo comportamento crítico.
- Documentação atualizada em `docs/`.
