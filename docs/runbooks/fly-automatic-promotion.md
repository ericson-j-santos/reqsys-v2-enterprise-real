# Runbook — Fly Automatic Environment Promotion

## Operação normal

Este workflow é **legado e manual-only**. Não possui gatilho por pós-merge nem reconciliação horária.

DEV é sempre validado no PC24x7 pelo locator assinado. Fly não é permitido em DEV. HML/PROD só podem usar o caminho Fly legado após acionamento explícito por `workflow_dispatch`, no SHA atual da `main`; PROD continua condicionado ao BACEN Production Hard Gate.

## Diagnóstico

1. Abra o run manual `Fly Automatic Environment Promotion`.
2. Confirme que `Validate DEV via PC24x7 public tunnel` terminou verde.
3. Consulte a decisão do estágio HML/PROD interrompido.
4. Baixe o artifact `fly-environment-evidence-<ambiente>-<fase>` quando HML/PROD forem executados.
5. Corrija somente a causa raiz indicada.
6. Reexecute manualmente com o SHA atual da `main`.

## Bloqueios esperados

- SHA obsoleto;
- locator PC24x7 ausente ou inválido;
- runtime DEV PC24x7 indisponível ou SHA divergente;
- secret Fly obrigatório ausente em HML/PROD;
- configuração crítica divergente;
- check Fly HML/PROD não saudável;
- BACEN sem autorização para produção;
- aprovação pendente no environment GitHub.

## Segurança

Não existe fallback Fly em DEV. Os artifacts Fly registram apenas nomes e estados dos secrets. Valores, tokens e senhas não são persistidos. Produção não possui bypass.
