# Security Baseline

Codigo: AI-GOV-SEC-001

## Regras obrigatorias

- Proteger credenciais e dados sensiveis.
- Evitar registro de dados pessoais ou credenciais em logs.
- Validar autenticacao e autorizacao por ambiente.
- Restringir origens de acesso conforme ambiente.
- Aplicar menor privilegio.
- Exigir correlation_id em auditoria.
- Separar configuracoes por ambiente.
- Aplicar principios de LGPD para dados pessoais, dados sensiveis, minimizacao, rastreabilidade e controle de acesso.

## Bloqueios

Producao deve ser bloqueada quando houver configuracao insegura ou ausencia de validacao critica.

Devem bloquear promocao para producao:

- autenticacao desabilitada;
- CORS irrestrito;
- JWT sem validacao real de emissor, audiencia e assinatura;
- logs com credenciais, tokens, connection strings ou dados pessoais sem mascaramento;
- auditoria sem correlation_id;
- tratamento de dados pessoais sem justificativa operacional e sem controle de acesso compatível com LGPD.

## Referencias cruzadas

- docs/ai-governance/00_PRIORITY_RULES.md
- docs/ai-governance/06-DEVOPS/QUALITY_GATES.md
- ReqSys: login, APIs, integracoes e pipelines.
