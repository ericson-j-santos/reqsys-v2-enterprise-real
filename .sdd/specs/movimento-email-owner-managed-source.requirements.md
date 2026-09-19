# Movimento Email — fonte institucional autogerida

## Objetivo

Criar uma fonte SQL real, controlada pelo proprietário do ReqSys, para a Prospecção Movimento em DEV privado, sem depender de infraestrutura, credenciais ou equipe de dados externa.

## Requisitos

1. Criar o banco `ReqSysMovimentoOwnerDev` no SQL Server local por autenticação integrada.
2. Criar o schema `owner_movimento` com os quatro datasets canônicos.
3. Criar as quatro views `dbo.vw_prospeccao_movimento_*` na fonte.
4. Não embutir seed de negócio sintético na fonte autogerida.
5. Permitir ingestão explícita de payload JSON com os quatro datasets e `data_referencia`.
6. A ingestão deve ser idempotente por SHA-256 do payload.
7. Sincronizar somente para `ReqSysMovimentoDev.movimento_src` com `source_tag=OWNER_MANAGED`.
8. Repetição com o mesmo estado deve resultar em `noop` sem escrita adicional.
9. Não criar login, usuário, senha ou segredo.
10. PROD permanece desabilitado.

## Critérios de aceite

1. O bootstrap físico retorna `status=passed` e `source_authority=owner_managed`.
2. Leitura independente confirma as quatro views na fonte e as quatro views no alvo.
3. A segunda execução do bootstrap também passa sem erro.
4. A suíte `tests/test_movimento_email_owner_source.py` passa integralmente.
5. O script não contém seed de negócio como `CLIENTE DEMO` ou marcadores `EQUIV-*`.
6. Servidor remoto ou banco sem sufixo `Dev` é rejeitado.
7. Payload com dataset, coluna ou data de referência divergente falha fechado.
8. Nenhum segredo é exigido ou exposto.
9. Nenhuma ação toca produção.
10. Dados reais só podem ser declarados após ingestão de payload operacional real; fixtures de validação não contam como dado de negócio real.
