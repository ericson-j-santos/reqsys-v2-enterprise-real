# Requisitos — redmine-version-security-gate

## Contexto

O ReqSys integra com o Redmine pela REST API usando API key. O Redmine não expõe
sua versão pela REST API de forma confiável; a própria documentação oficial orienta
consultar **Administration > Information** ou a instalação do servidor. Portanto,
o preflight não deve tentar deduzir versão a partir de endpoints existentes.

A baseline foi revalidada em 18/10/2026 contra o Security Advisories oficial.
Os avisos #44467 e #44468 incluem divulgação de dados privados pela REST API e
foram corrigidos nas versões 6.1.5 e 7.0.2. A série 6.0 permanece mantida upstream,
mas não possui correção homologada desses avisos: bloqueá-la sem classificá-la
como EOL. Esta revisão substitui os mínimos de 28/09/2026.

Fonte: https://www.redmine.org/projects/redmine/wiki/Security_Advisories

## Critérios de aceite

1. O preflight deve exigir uma versão Redmine explicitamente informada por fonte
   operacional verificável, sem tratá-la como segredo.
2. Redmine 6.0 deve falhar com `redmine_version_sem_correcao_homologada`, sem
   inventar uma versão corrigida nem classificar a série como EOL.
3. Redmine 6.1 deve exigir versão >= 6.1.5.
4. Redmine 7.0 deve exigir versão >= 7.0.2.
5. Redmine 5.x ou anterior deve falhar como EOL.
6. Séries não homologadas, inclusive futuras, devem falhar fechado até atualização
   consciente da política.
7. Versão ausente, malformada, de desenvolvimento ou com sufixo não homologado
   deve impedir o preflight de declarar sucesso. Aceitar somente release ou
   `.stable` com revisão numérica opcional.
8. O teste automatizado deve incluir casos positivos, limites exatos, versões
   vulneráveis antes aceitas, EOL, séries futuras, idempotência e controle negativo.
9. Nenhum segredo, ambiente, deploy ou instância Redmine real deve ser alterado
   por este incremento de política.
10. O E2E real ReqSys ↔ Redmine continua pendente enquanto a instância DEV não
    estiver configurada; testes isolados não podem ser apresentados como E2E real.
