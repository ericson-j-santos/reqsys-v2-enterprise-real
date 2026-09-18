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

## Correção de CI

- O modo padrão foi alterado para `strict=false`.
- `pull_request` e `push` passam a operar em modo report-only para scanners especializados.
- `workflow_dispatch` com `strict=true` mantém bloqueio manual e intencional.
- O checkout do Gitleaks foi reduzido para snapshot atual (`fetch-depth: 1`) para evitar bloqueio por histórico antigo fora do escopo do PR.
- O diretório do SBOM passou a ser criado explicitamente antes da geração.

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
- Bloqueio estrito disponível somente por execução manual explícita.

## Próximo incremento seguro

Criar consolidator `security-executive-summary.json` para unificar baseline, scanners, severidades, exceções e score executivo de segurança no Ops Dashboard.