# Requisitos — redmine-version-security-gate

## Contexto

O ReqSys integra com o Redmine pela REST API usando API key. O Redmine não expõe
sua versão pela REST API de forma confiável; a própria documentação oficial orienta
consultar **Administration > Information** ou a instalação do servidor. Portanto,
o preflight não deve tentar deduzir versão a partir de endpoints existentes.

A baseline deste incremento acompanha as correções de segurança publicadas para
Redmine 6.0.11, 6.1.4 e 7.0.1. Séries não homologadas ficam bloqueadas por padrão.

## Critérios de aceite

1. O preflight deve exigir uma versão Redmine explicitamente informada por fonte
   operacional verificável, sem tratá-la como segredo.
2. Redmine 6.0 deve exigir versão >= 6.0.11.
3. Redmine 6.1 deve exigir versão >= 6.1.4.
4. Redmine 7.0 deve exigir versão >= 7.0.1.
5. Redmine 5.x ou anterior deve falhar como EOL.
6. Séries não homologadas, inclusive futuras, devem falhar fechado até atualização
   consciente da política.
7. Versão ausente ou malformada deve impedir o preflight de declarar sucesso.
8. O teste automatizado deve incluir casos positivos, versões vulneráveis, EOL,
   séries futuras e um controle negativo conhecido.
9. Nenhum segredo, ambiente, deploy ou instância Redmine real deve ser alterado
   por este incremento.
10. O E2E real ReqSys ↔ Redmine continua pendente enquanto a instância DEV não
    estiver configurada; testes isolados não podem ser apresentados como E2E real.
