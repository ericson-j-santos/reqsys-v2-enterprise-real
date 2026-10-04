# Security Baseline — ReqSys

## Objetivo

Estabelecer um baseline mínimo, automatizado e rastreável de segurança para impedir que riscos críticos avancem para `main`, staging ou produção.

Este baseline não substitui auditoria humana, pentest, revisão arquitetural ou ferramentas especializadas. Ele funciona como primeiro gate objetivo de engenharia segura.

## Decisão arquitetural

O ReqSys deve validar segurança no CI antes de merge/deploy, com evidência gerada em artifact versionado.

A decisão recomendada é manter o gate inicialmente com validações determinísticas, offline e sem dependência de serviços externos, reduzindo falso bloqueio por indisponibilidade de ferramentas SaaS.

## Controles cobertos no incremento inicial

| Controle | Status | Bloqueia CI? |
|---|---:|---:|
| Arquivos `.env` reais versionados | Ativo | Sim |
| Segredos hardcoded | Ativo | Sim |
| Authorization/Bearer hardcoded | Ativo | Sim |
| Chave privada versionada | Ativo | Sim |
| CORS com wildcard | Ativo | Sim |
| TLS desabilitado (`verify=False`) | Ativo | Sim |
| MSAL hardcoded | Ativo | Não, severidade alta |
| URLs de ambiente hardcoded | Ativo | Não, severidade alta |
| Logs com token/CPF/senha provável | Ativo | Não, severidade alta |

## Variáveis obrigatórias por ambiente

A configuração deve ser segregada por DEV/STG/PROD.

```env
REQSYS_ENV=dev|stg|prod
API_BASE_URL=
PUBLIC_BASE_URL=
ALLOWED_ORIGINS=
MSAL_CLIENT_ID=
MSAL_TENANT_ID=
MSAL_REDIRECT_URI=
MSAL_AUTHORITY=
MSAL_SCOPES=
JWT_ISSUER=
JWT_AUDIENCE=
```

## Regras canônicas

### 1. Secrets

Não versionar:

- `.env` real;
- token;
- client secret;
- senha;
- API key;
- private key;
- connection string sensível.

Usar:

- GitHub Secrets;
- variáveis por ambiente;
- secret manager quando disponível;
- rotação periódica.

### 2. MSAL/Azure

Não usar `client_id`, `tenant_id`, `redirect_uri` ou authority diretamente no código.

Todos os valores devem vir de configuração por ambiente.

### 3. CORS

Proibido:

```python
allow_origins=["*"]
```

Obrigatório:

```python
allow_origins=settings.allowed_origins
```

### 4. TLS

Proibido:

```python
verify=False
```

Quando houver CA corporativa, usar bundle configurado por variável:

```env
REQSYS_CA_BUNDLE=/path/ca.pem
```

### 5. Logs e LGPD

Logs devem mascarar:

- CPF;
- e-mail;
- Authorization;
- access_token;
- refresh_token;
- client_secret;
- senha;
- payload sensível.

Todo log operacional relevante deve conter `correlation_id`.

### 6. Agentes e automações

Ações críticas exigem aprovação humana ou gate formal:

| Ação | Exige aprovação/gate |
|---|---:|
| Merge em `main` | Sim |
| Deploy em produção | Sim |
| Execução SQL real | Sim |
| Alteração de secrets | Sim |
| Chamada a API corporativa sensível | Sim |
| Rollback produtivo | Sim |

## Evidências geradas

O workflow `Security Baseline Gate` publica o artifact:

```text
security-baseline-report
├── security-baseline-report.json
└── security-baseline-report.md
```

## Próximos incrementos recomendados

1. Integrar `gitleaks` como secret scan especializado.
2. Integrar `pip-audit` para dependências Python.
3. Integrar `npm audit` para frontend.
4. Gerar SBOM CycloneDX.
5. Adicionar CodeQL/SAST.
6. Publicar score executivo de segurança no Ops Dashboard.
7. Bloquear produção quando houver critical/high não aceito por exceção formal.

## Critério de pronto

O baseline está pronto quando:

- o workflow executa em PR e `main`;
- o relatório JSON/Markdown é publicado;
- achados críticos bloqueiam CI;
- regras e recomendações estão documentadas;
- falsos positivos podem ser tratados por ajuste explícito do validador, nunca por ignorar o gate.
