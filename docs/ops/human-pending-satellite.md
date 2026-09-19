# Human Pending Satellite

Rotina automática do ReqSys para reduzir pendências humanas ao mínimo indispensável.

## Objetivo

A rotina tenta primeiro a remediação automática allowlisted das pendências conhecidas, reconcilia runs recentes e só depois varre issues abertas. Ela identifica somente dependências que ainda exigem decisão, autorização, credencial, permissão ou evidência externa real e captura autorizações explícitas já registradas por responsáveis confiáveis.

Ela não substitui fatos externos por aprovação textual. Documento, corpus, MFA, contrato, assinatura, permissão, efeito de DNS, billing, aceite ou evidência operacional precisam existir de fato.

## Execução

- agendada a cada hora pelo workflow `Human Pending Satellite`;
- antes de notificar, `human_pending_auto_remediation.py` pode disparar, com cooldown e idempotência, os workflows de #1130, #1520 e #1532;
- run automático em andamento ou recém-concluído com sucesso suprime escalada humana quando não existe follow-up interativo real;
- disponível também por `workflow_dispatch`;
- modo `dry_run` permite validar sem comentar nas issues;
- gera artefato sanitizado `evidence.json` com retenção de 30 dias.

## Controles contra falso positivo

- não escala falha técnica isolada de CI/build/teste;
- só reconhece aprovação explícita de OWNER/MEMBER/COLLABORATOR;
- aprovação capturada vira referência de autorização, não prova do fato externo;
- comentários têm assinatura idempotente para evitar repetição sem mudança de estado;
- não armazena segredos, dados pessoais, conteúdo OCR bruto ou documentos reais no GitHub.

## Escopo de pendências humanas

Inclui aprovação/review obrigatória, decisão de merge prevista por política, conflito que dependa de escolha, approval de environment/deployment, secrets/variables/credenciais externas, permissões, branch protection, DNS/domínio, billing/limites, aceite operacional, confirmação de produção, decisão arquitetural e evidências reais com revisão humana.

O Coordinator continua responsável por CI vermelho corrigível, falhas técnicas, correção de código/configuração e demais ações automatizáveis.


## Credencial GitHub para arquivos de workflow

A #1130 não deve mais depender de `GH_PAT_ACTIONS`. O watcher e a promoção governada usam token de instalação efêmero da GitHub App `reqsys-stack-rebase`, solicitando somente `contents: write`, `workflows: write` e, na promoção, `pull-requests: write`.

Se a instalação ainda não tiver `Workflows: read/write`, o sistema falha fechado com `app_workflows_permission_missing`. A única ação humana residual é aprovar essa permissão administrativa no GitHub; não é necessário gerar ou rotacionar PAT.
