# Human Pending Satellite

Rotina automática do ReqSys para reduzir pendências humanas ao mínimo indispensável.

## Objetivo

A rotina varre issues abertas, identifica somente dependências que exigem decisão, autorização, credencial, permissão ou evidência externa real e tenta capturar automaticamente autorizações explícitas já registradas por responsáveis confiáveis.

Ela não substitui fatos externos por aprovação textual. Documento, corpus, MFA, contrato, assinatura, permissão, efeito de DNS, billing, aceite ou evidência operacional precisam existir de fato.

## Execução

- agendada a cada hora pelo workflow `Human Pending Satellite`;
- disponível também por `workflow_dispatch`;
- modo `dry_run` permite validar sem comentar nas issues;
- gera artefato sanitizado `evidence.json` com retenção de 30 dias.

## Controles contra falso positivo

- não escala falha técnica isolada de CI/build/teste;
- cabeçalhos genéricos como `Responsável` não são tratados como intenção humana;
- a frase genérica `evidência real` não basta para escalar uma issue;
- menções genéricas ou futuras a `aprovação humana` não geram alerta antes do gate realmente estar ativo; use linguagem explícita (`ação humana`, `aprovação obrigatória`) ou `human-gate:*` quando a intervenção for atual;
- dependência de fonte corporativa externa é classificada separadamente, por exemplo SQL/DSN ou RDL/RDS de negócio;
- só reconhece aprovação e mudança de gate em comentários de OWNER/MEMBER/COLLABORATOR;
- comentários confiáveis podem encerrar um gate humano histórico e comentários posteriores podem reabri-lo;
- `human-gate:resolved` e `satellite:suppress-human` suprimem alertas; outros labels `human-gate:*` funcionam como sinal explícito;
- aprovação capturada vira referência de autorização, não prova do fato externo;
- comentários têm assinatura idempotente para evitar repetição sem mudança de estado;
- não armazena segredos, dados pessoais, conteúdo OCR bruto ou documentos reais no GitHub.

## Escopo de pendências humanas

Inclui aprovação/review obrigatória, decisão de merge prevista por política, conflito que dependa de escolha, approval de environment/deployment, secrets/variables/credenciais externas, permissões, branch protection, DNS/domínio, billing/limites, aceite operacional, confirmação de produção, decisão arquitetural e evidências reais com revisão humana.

O Coordinator continua responsável por CI vermelho corrigível, falhas técnicas, correção de código/configuração e demais ações automatizáveis.

Quando uma dependência externa de negócio for legítima, o satélite deve pedir apenas a informação impossível de inferir: fonte autorizada, referência da consulta/regra e identidade de menor privilégio. Segredos nunca devem ser enviados por chat, issue ou comentário.
