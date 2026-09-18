# Movimento Email — fonte SQL separada de DEV

## Requisito 1 — origem independente
Deve existir um banco SQL Server separado do banco canônico, representando a origem legado/SSRS em DEV, com schema `legacy_ssrs` e quatro datasets persistentes.

## Requisito 2 — sincronização governada
A cópia `legacy_ssrs.* → movimento_src.*` deve usar conexões separadas, transação no destino e convergir por `source_tag`, sem duplicação em reexecução.

## Requisito 3 — SSRS verificável
Devem existir RDL/RDS sem credenciais apontando para o banco de origem DEV e para os quatro objetos `legacy_ssrs.*`.

## Requisito 4 — segurança
Não criar login, usuário, senha ou segredo em Git/chat. DEV usa autenticação integrada; a origem corporativa futura continua externa.

## Critérios de aceite (Acceptance Criteria)
1. `ReqSysMovimentoSourceDev` é criado/reutilizado no SQL Server DEV.
2. O schema `legacy_ssrs` contém quatro tabelas.
3. Seed E2E gera contagens 2/1/1/1.
4. Sincronização produz as mesmas contagens nas quatro views V2.
5. Reexecução mantém as mesmas contagens.
6. Controle negativo por data retorna 0.
7. RDL/RDS não contêm credenciais.
8. Testes automatizados passam.
9. Pre-PR Readiness passa no HEAD exato com `behind_by=0`.
10. Nenhuma evidência DEV é apresentada como origem corporativa validada.
