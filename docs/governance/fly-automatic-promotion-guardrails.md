# Guard rails — promoção automática Fly

1. Somente o SHA corrente da `main` é elegível.
2. DEV precisa estar validado antes de STG.
3. STG precisa estar validado antes de PROD.
4. PROD exige autorização positiva do BACEN Production Hard Gate.
5. O environment GitHub do estágio não pode ser ignorado.
6. Artifact ausente, JSON inválido ou evidência divergente bloqueia.
7. Secret obrigatório ausente ou não implantado bloqueia.
8. Valores de secrets nunca são persistidos.
9. O deploy é omitido quando o ambiente já está sincronizado.
10. Falha não dispara rollback destrutivo automático.
