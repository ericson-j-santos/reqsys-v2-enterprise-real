# Runbook — Fly Automatic Environment Promotion

## Operação normal

O workflow inicia após o validador pós-merge, por reconciliação horária ou manualmente. Ele resolve o SHA atual da `main`, captura DEV e só executa deploy quando as evidências apontam drift. Após validação estrita, repete o processo em STG e, se autorizado pelo BACEN Production Hard Gate, em PROD.

## Diagnóstico

1. Abra o run `Fly Automatic Environment Promotion`.
2. Consulte a decisão do estágio interrompido.
3. Baixe o artifact `fly-environment-evidence-<ambiente>-<fase>`.
4. Verifique `decision.json` e `blocking_issues`.
5. Corrija somente a causa raiz indicada.
6. Reexecute a reconciliação com o SHA atual da `main`.

## Bloqueios esperados

- SHA obsoleto;
- secret obrigatório ausente ou ainda não implantado;
- configuração crítica divergente;
- máquina abaixo do mínimo;
- check Fly não saudável;
- endpoints obrigatórios indisponíveis;
- build SHA divergente;
- login ou redirect inválido;
- BACEN sem autorização para produção;
- aprovação pendente no environment GitHub.

## Segurança

Os artifacts registram apenas nomes e estados dos secrets. Valores, tokens e senhas não são persistidos. Produção não possui bypass e continua sujeita às regras do environment `production`.
