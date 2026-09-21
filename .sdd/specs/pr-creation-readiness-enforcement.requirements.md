# Requisitos — Enforcement global de publicação de PR

## Objetivo

Eliminar ciclos recorrentes de CI causados por automações que abrem PRs para `main`
antes de comprovar prontidão determinística do HEAD exato.

## Requisitos

1. Nenhum workflow pode executar `gh pr create --base main` diretamente.
2. Nenhum workflow pode executar `POST .../pulls` com `base=main` diretamente.
3. Rotas automatizadas para `main` devem usar `scripts/auto_open_agent_pr.py`.
4. O autoabridor deve exigir `Pre-PR Readiness Gate=success` no mesmo HEAD e
   revalidar que a branch está estritamente à frente da base atual.
5. Corpo e título específicos da automação devem ser preserváveis.
6. A opção de criar PR não-draft só pode ocorrer depois do readiness verde.
7. Branches geradas por automação devem usar credencial que permita disparar o
   evento de push/PR; ausência da credencial deve falhar fechado, sem criar PR.
8. `PR Creation Path Guard` deve executar em todo PR para `main` e ser
   obrigatório na `Governed Merge Queue`.
9. O scanner deve ter controle negativo para criação direta via CLI e REST.
10. Promoções para bases diferentes de `main` permanecem fora deste contrato.
11. Nenhuma alteração deste incremento executa merge, deploy ou produção.

## Critérios de aceite

- scanner do repositório retorna `valid=true`;
- testes negativos rejeitam CLI e REST diretos para `main`;
- testes comprovam que o autoabridor preserva corpo e só cria PR pronta após gate verde;
- rotas Domain Coverage, Backup Rollout e Governed Workflow Artifact Promotion não
  contêm criação direta de PR para `main`;
- política de estabilidade do SHA exige `PR Creation Path Guard`;
- Pre-PR Readiness e CI da própria correção ficam verdes no mesmo HEAD.
