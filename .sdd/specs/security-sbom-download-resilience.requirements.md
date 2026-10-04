# Security SBOM Download Resilience — Requisitos

## Objetivo

Eliminar falhas transitórias recorrentes do job `SBOM CycloneDX` causadas pelo download do Syft via GitHub Releases, sem reduzir o rigor do scanner ou aceitar evidência ausente.

## Classificação

`gap_fix`.

## Requisitos

1. Manter o Syft fixado em `1.51.0`.
2. Baixar diretamente o artefato oficial Linux AMD64 da release imutável.
3. Aplicar retentativas limitadas para erros HTTP transitórios, incluindo 5xx.
4. Verificar o SHA-256 oficial do arquivo antes da instalação.
5. Falhar imediatamente se download, checksum, extração, execução do Syft ou geração do SBOM falhar.
6. Desabilitar apenas a checagem de atualização do Syft durante a geração; não desabilitar scanner nem validações.
7. Gerar `artifacts/security-scanners/sbom/reqsys-sbom.cyclonedx.json` e comprovar que o arquivo não está vazio.
8. Preservar o upload do SBOM como evidência obrigatória.

## Controles negativos

- Não usar `continue-on-error` no job SBOM.
- Não usar versão `latest` ou binário sem checksum.
- Não suprimir falha quando o artefato SBOM estiver ausente.
- Não introduzir segredo, permissão de escrita ou deploy.

## Critérios de aceite

- `tests/test_security_scanner_sbom_resilience.py` verde.
- `Pre-PR Readiness Gate` verde no HEAD final.
- Job `SBOM CycloneDX` verde no mesmo HEAD.
- Workflow `Security Specialized Scanners` verde no mesmo HEAD.
