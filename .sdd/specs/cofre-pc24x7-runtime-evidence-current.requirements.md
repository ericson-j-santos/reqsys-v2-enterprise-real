# Cofre Runtime Evidence Gate — PC24x7 DEV atual

## Contexto
A issue #1760 exige evidência nova do ciclo completo do Cofre em DEV no SHA atual da main. O workflow legado ainda dependia de Fly.io, embora o runtime canônico DEV seja PC24x7.

## Requisitos
1. DEV deve usar somente `PC24X7_DEV_BASE_URL`; URL Fly.io deve falhar fechada.
2. O job mutável deve executar em runner self-hosted PC24x7 rotulado `pc24x7` e `reqsys-dev`.
3. O container autorizado deve ser exclusivamente `wt-pc24x7-piloto-api-1`.
4. Antes do restart, o executor deve provar projeto Compose, serviço, SHA, mount somente leitura da passphrase e volume persistente.
5. O restart deve atingir somente a API DEV e aguardar health terminal.
6. `cofre_runtime_evidence.py` deve autenticar JWT administrativo com `Authorization: Bearer`.
7. Token S2S apresentado e inválido/revogado deve retornar 401 mesmo sem `VAULT_API_TOKEN` legado configurado.
8. Estado transitório deve permanecer criptografado e ser removido ao final.
9. Artifact e resumo não podem conter JWT, passphrase, token S2S ou segredo de teste.
10. STG/PROD permanecem bloqueados neste incremento.
11. O deploy operacional de DEV deve ser restrito à API, validar SHA/árvore limpa e possuir rollback para o runtime anterior.

## Critérios de aceite
- testes dirigidos passam no SHA da branch;
- workflow não contém Fly.io/flyctl/FLY_API_TOKEN;
- controle negativo detecta SHA divergente;
- E2E novo DEV usa correlation_id próprio, same-SHA, restart, persistência, auditoria e cleanup;
- `production_touched=false`;
- nenhum merge automático.
