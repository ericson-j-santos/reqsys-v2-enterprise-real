# Changelog — Security Specialized Scanners

## Resumo

Adicionado workflow dedicado para scanners especializados de segurança no ReqSys.

## Arquivos adicionados

- `.github/workflows/security-specialized-scanners.yml`
- `docs/security/SECURITY_SPECIALIZED_SCANNERS.md`
- `docs/changelog/security-specialized-scanners.md`

## Scanners adicionados

- Gitleaks Secret Scan.
- pip-audit para dependências Python.
- npm audit para dependências Node/frontend.
- SBOM CycloneDX via Anchore.
- CodeQL/SAST para Python e JavaScript/TypeScript.

## Evidências

Artifacts esperados:

- `pip-audit-report`
- `npm-audit-report`
- `reqsys-sbom-cyclonedx`

CodeQL publica evidências no GitHub Code Scanning.

## Guardrails

- Sem deploy.
- Sem alteração funcional no runtime.
- Sem dependência de secrets customizados.
- Jobs separados para facilitar rastreabilidade.
- Permissões declaradas e restritas ao necessário.

## Próximo incremento seguro

Criar consolidator `security-executive-summary.json` para unificar baseline, scanners, severidades, exceções e score executivo de segurança no Ops Dashboard.
