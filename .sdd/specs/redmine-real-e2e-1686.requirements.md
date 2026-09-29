# Requisitos — redmine-real-e2e-1686

## Objetivo

Provar em um ambiente DEV isolado o comportamento já implementado do lifecycle
ReqSys ↔ Redmine, usando uma instância real do Redmine e evidência vinculada ao
SHA exato do ReqSys.

## Critérios de aceite

1. A versão Redmine deve passar no gate antes de qualquer validação funcional.
2. A autenticação real deve resolver um usuário Redmine sem expor a credencial.
3. Uma leitura real da issue deve incluir journals.
4. Alterações de título e descrição originadas no ReqSys devem resultar em PUT
   real no Redmine e ser confirmadas por leitura independente.
5. Alterações Redmine de status, responsável, progresso e journal devem ser
   confirmadas no checkpoint/auditoria do ReqSys.
6. Replay sem alteração deve produzir zero mutações, zero novos eventos de
   auditoria e nenhum avanço do estado persistido.
7. Uma issue inexistente deve provar falha, backoff, segunda tentativa,
   quarentena e replay ignorado sem duplicar estado de controle.
8. A versão 6.1.3 deve funcionar como controle negativo e permanecer bloqueada.
9. A evidência deve registrar SHA, ambiente, requirement/issue IDs e
   correlation_id, mas nunca o valor de REDMINE_API_KEY.
10. Falha do harness deve registrar apenas tipo e referência genérica, sem
    serializar texto de exceção possivelmente sensível.
