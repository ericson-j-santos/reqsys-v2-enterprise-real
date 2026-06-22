# Security Baseline

Codigo: AI-GOV-SEC-001

## Regras obrigatorias

- Atender LGPD, minimizacao de dados e finalidade explicita no tratamento.
- Proteger credenciais e dados sensiveis.
- Evitar registro de dados pessoais ou credenciais em logs.
- Validar autenticacao e autorizacao por ambiente.
- Restringir origens de acesso conforme ambiente.
- Aplicar menor privilegio.
- Exigir correlation_id em auditoria.
- Separar configuracoes por ambiente.

## Bloqueios

Producao deve ser bloqueada quando houver configuracao insegura ou ausencia de validacao critica.

## Referencias cruzadas

- docs/ai-governance/00_PRIORITY_RULES.md
- docs/ai-governance/06-DEVOPS/QUALITY_GATES.md
- ReqSys: login, APIs, integracoes e pipelines.
