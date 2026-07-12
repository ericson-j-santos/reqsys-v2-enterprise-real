# Plano de login hibrido com certificado digital

## Objetivo

Adicionar ao ReqSys um fluxo de login hibrido que mantenha Microsoft Entra ID como provedor corporativo principal e acrescente certificado digital como provedor alternativo, terminando sempre no JWT interno do ReqSys e no RBAC existente.

## Escopo implementado

- Configuracao por ambiente:
  - `CERT_LOGIN_ENABLED`
  - `CERT_TRUST_STORE_PATH`
  - `CERT_ALLOWED_ISSUERS`
  - `CERT_CHALLENGE_TTL_SECONDS`
- Endpoints backend:
  - `POST /v1/auth/certificate/challenge`
  - `POST /v1/auth/certificate/verify`
  - `GET /v1/auth/config` com `certificate_enabled`
- Validacao backend:
  - desafio temporario de uso unico;
  - validade temporal do certificado;
  - filtro opcional por emissor;
  - validacao opcional contra trust store;
  - verificacao de assinatura SHA-256 RSA/ECDSA do desafio;
  - extracao de identidade por e-mail, CPF, CNPJ, CN e serial.
- Frontend:
  - botao "Entrar com certificado digital";
  - integracao com `window.ReqSysCertificateAgent.signChallenge`;
  - persistencia de sessao pelo mesmo store de auth.

## Arquitetura alvo

1. Usuario abre `/login`.
2. Frontend chama `/v1/auth/config`.
3. Se `certificate_enabled=true`, exibe "Entrar com certificado digital".
4. Frontend chama `/v1/auth/certificate/challenge`.
5. Agente local/Web PKI assina o desafio com o certificado do usuario.
6. Frontend envia certificado publico, desafio e assinatura para `/v1/auth/certificate/verify`.
7. Backend valida certificado e assinatura.
8. Backend mapeia identidade para papel/permissoes.
9. Backend emite JWT interno com `auth_provider=certificate`.
10. Frontend salva a sessao e segue para o app.

## Decisoes

- O ReqSys nao recebe chave privada.
- O desafio e de uso unico e expira por TTL.
- O login por certificado fica desligado por padrao.
- Em producao, se `CERT_LOGIN_ENABLED=true`, `CERT_TRUST_STORE_PATH` e obrigatorio.
- Microsoft Entra ID continua suportado e pode ser usado com Certificate-Based Authentication quando o tenant tiver essa politica.

## Pendencias para producao

- Escolher o mecanismo de assinatura local:
  - Web PKI/local agent para A3/token;
  - componente corporativo instalado;
  - ou mTLS no gateway, se a borda suportar certificado de cliente.
- Provisionar trust store:
  - CAs corporativas;
  - cadeia ICP-Brasil quando aplicavel;
  - processo de atualizacao e rotacao.
- Definir politica de revogacao:
  - CRL/OCSP online;
  - tolerancia a indisponibilidade;
  - cache e auditoria.
- Criar cadastro/vinculo de identidade:
  - CPF/CNPJ/e-mail do certificado;
  - usuario ReqSys;
  - papel inicial;
  - revisao periodica.
- Adicionar logs operacionais:
  - sucesso/falha por provider;
  - falha por assinatura;
  - falha por cadeia;
  - falha por expiracao/revogacao.

## Rollout recomendado

1. Desenvolvimento:
   - manter `CERT_LOGIN_ENABLED=false`;
   - rodar testes automatizados do servico e endpoints;
   - validar UI sem agente local.
2. Homologacao:
   - habilitar `CERT_LOGIN_ENABLED=true`;
   - configurar trust store de homologacao;
   - integrar agente local/Web PKI;
   - testar A1, A3 e erro de certificado expirado.
3. Producao piloto:
   - liberar para grupo pequeno;
   - monitorar eventos `LOGIN_CERTIFICADO`;
   - comparar identidade extraida com cadastro corporativo.
4. Producao geral:
   - ativar para todos os perfis aprovados;
   - manter Entra ID como fallback;
   - revisar auditoria e revogacao.

## Checklist de ativacao por ambiente

### Desenvolvimento

- `CERT_LOGIN_ENABLED=false` no `.env` local por padrao.
- Executar `pytest tests/test_azure_auth.py tests/test_certificate_auth.py`.
- Executar build do frontend.
- Validar que `/v1/auth/config` retorna `certificate_enabled=false`.

### Homologacao

- Criar diretorio seguro para trust store, por exemplo `/app/config/cert-trust`.
- Instalar certificados CA de homologacao no `CERT_TRUST_STORE_PATH`.
- Definir:
  - `CERT_LOGIN_ENABLED=true`
  - `CERT_TRUST_STORE_PATH=/app/config/cert-trust`
  - `CERT_ALLOWED_ISSUERS=<issuer esperado, opcional>`
  - `CERT_CHALLENGE_TTL_SECONDS=300`
- Publicar o agente local/Web PKI homologado para os usuarios piloto.
- Validar A1/A3 com assinatura de desafio real.
- Validar erro esperado para certificado expirado, emissor nao permitido e assinatura invalida.
- Conferir evento `LOGIN_CERTIFICADO` na auditoria.

### Producao

- Repetir trust store com CAs produtivas aprovadas.
- Validar politica de revogacao ICP-Brasil/corporativa antes de ampliar o publico.
- Ativar `CERT_LOGIN_ENABLED=true` apenas depois de existir `CERT_TRUST_STORE_PATH`.
- Manter Microsoft Entra ID habilitado como fallback corporativo.
- Executar piloto com usuarios de baixo risco operacional.
- Promover para geral somente depois de revisar auditoria, suporte e rollback.

## Estado final do incremento

- Codigo do fluxo hibrido: pronto.
- UI e contrato de agente local/Web PKI: pronto.
- Gates de seguranca de producao: pronto.
- Testes automatizados do backend: pronto.
- Ativacao produtiva: depende da trust store real, do agente local/Web PKI escolhido e da politica de revogacao aprovada.

## Criterios de aceite

- `GET /v1/auth/config` informa corretamente quando certificado esta habilitado.
- Login certificado desligado retorna 503 nos endpoints dedicados.
- Desafio expirado ou reutilizado retorna 401.
- Assinatura invalida retorna 401.
- Certificado valido + assinatura correta emite JWT interno.
- Usuario autenticado por certificado recebe permissoes RBAC.
- Producao nao sobe com `CERT_LOGIN_ENABLED=true` sem trust store.
