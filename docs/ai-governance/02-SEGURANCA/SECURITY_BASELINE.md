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
- Aplicar LGPD como baseline obrigatorio para coleta, tratamento, armazenamento, mascaramento e auditoria de dados pessoais.

## Bloqueios

Producao deve ser bloqueada quando houver configuracao insegura ou ausencia de validacao critica.

Bloquear producao quando qualquer fluxo de IA, RAG, Codex, analytics ou integracao externa puder expor credenciais, dados pessoais, PII, connection strings ou tokens em logs, respostas, traces ou relatórios.

## Requisitos minimos LGPD

- Mascarar dados pessoais em logs, auditoria e telemetria.
- Evitar persistencia de prompts com PII sem base legal, finalidade e rastreabilidade.
- Registrar `correlation_id` sem registrar segredo ou dado pessoal desnecessario.
- Aplicar menor privilegio em providers de IA, conectores e webhooks.
- Validar que respostas de IA nao retornem credenciais, CPF, tokens, connection strings ou dados sensiveis.

## Referencias cruzadas

- docs/ai-governance/00_PRIORITY_RULES.md
- docs/ai-governance/06-DEVOPS/QUALITY_GATES.md
- ReqSys: login, APIs, integracoes e pipelines.
