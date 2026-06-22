# ADR-030 — Governed Dev Auto Merge

## Status

Aceita para incremento inicial.

## Contexto

O ReqSys precisa acelerar merges seguros para desenvolvimento sem reduzir governança em homologação e produção.

O auto-merge nativo do GitHub é limitado para as necessidades do ecossistema ReqSys, especialmente em relação a:

- políticas customizadas por ambiente;
- evidência auditável;
- bloqueios por tipo de arquivo;
- rastreabilidade com `correlation_id`;
- separação entre desenvolvimento, homologação e produção.

## Decisão

Implementar workflow manual de auto-merge governado somente para PRs com base `dev`.

Homologação e produção continuam fora do auto-merge e devem seguir promoção governada com aprovação humana explícita.

## Consequências positivas

- Reduz tempo de integração em desenvolvimento.
- Mantém produção protegida.
- Permite gates customizados.
- Gera evidência auditável.
- Evita dependência exclusiva de `allow_auto_merge` nativo.

## Consequências negativas

- Requer disciplina operacional para usar `dry_run=true` antes de uso real.
- Requer existência e governança da branch `dev`.
- Não substitui revisão técnica em mudanças sensíveis.

## Regras

Auto-merge em dev só pode ocorrer quando:

- PR está aberto;
- PR não está em draft;
- base é `dev`;
- PR está mergeável;
- risco é baixo;
- não há alteração em áreas bloqueadas;
- aprovação humana existe quando `require_manual_approval=true`;
- `dry_run=false` foi definido conscientemente.

## Áreas bloqueadas

- auth;
- security;
- secrets;
- vault/cofre;
- JWT;
- CORS;
- deploy;
- Fly.io;
- infra;
- banco/migrations;
- homologação;
- produção;
- release;
- workflows de deploy/release/prod;
- arquivos `.env`.

## Ambiente

| Ambiente | Política |
|---|---|
| dev | auto-merge governado permitido para baixo risco |
| homolog | promotion governada/manual |
| prod | aprovação humana explícita |
