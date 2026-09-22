# Changelog — Security Baseline Gate

## Resumo

Adicionado gate inicial de segurança para o ReqSys com validação automatizada em GitHub Actions, geração de evidência e documentação canônica.

## Arquivos adicionados

- `.github/workflows/security-baseline-gate.yml`
- `scripts/validate_security_baseline.py`
- `docs/security/SECURITY_BASELINE.md`
- `docs/changelog/security-baseline-gate.md`

## Validações implementadas

- Secret scan heurístico.
- Detecção de `.env` real versionado.
- Bloqueio de CORS wildcard.
- Bloqueio de TLS desabilitado.
- Detecção de hardcode MSAL/Azure.
- Detecção de URLs de ambiente hardcoded.
- Detecção de logs com tokens, CPF, senha ou segredo provável.

## Evidência publicada

O workflow publica artifact `security-baseline-report` contendo:

- `security-baseline-report.json`
- `security-baseline-report.md`

## Guardrails

- Offline/read-only.
- Sem chamada externa.
- Sem leitura de secrets.
- Sem dependência de SaaS externo.
- Achados críticos bloqueiam CI em modo strict.
- Achados high são reportados para priorização incremental.

## Próximo incremento seguro

Integrar scanners especializados ao gate:

1. Gitleaks para secret scanning.
2. pip-audit para dependências Python.
3. npm audit para frontend.
4. SBOM CycloneDX.
5. CodeQL/SAST.
