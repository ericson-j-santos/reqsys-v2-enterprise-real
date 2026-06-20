# ADR-0002 — Segurança e Gates de Produção

Status: aceito
Data: 2026-06-20

## Contexto

O ReqSys pode manipular requisitos, integrações, automações, dados operacionais e fluxos sensíveis. Produção não pode aceitar configuração insegura ou ausência de rastreabilidade.

## Decisão

Produção deve ser bloqueada quando qualquer gate crítico falhar.

Gates mínimos:

- Autenticação desabilitada em fluxo protegido.
- CORS permissivo em ambiente produtivo.
- Token de acesso sem validação real de emissor, público e expiração.
- Resposta gerada sem base verificável quando a funcionalidade exigir fonte.
- Ingestão administrativa sem autorização adequada.
- Registro operacional contendo credenciais, identificadores pessoais ou detalhes de conexão.
- Auditoria sem identificador de correlação.
- Endpoint administrativo exposto sem autorização e rastreabilidade.

## Consequências

- Segurança passa a ser requisito de entrega, não etapa opcional.
- Pipelines devem falhar explicitamente em caso de configuração insegura.
- Logs e auditoria devem ser tratados como componentes de produto.

## Critérios de aceite

- Gates automatizados sempre que possível.
- Revisão manual obrigatória quando o gate não puder ser automatizado.
- Evidência registrada no PR ou release note.
