# GitLab DevSecOps Baseline

## Objetivo

Definir a linha de base de DevSecOps da ReqSys v2 Enterprise GitLab Edition.

## Capacidades ativas

| Capacidade | Estado | Evidência |
|---|---|---|
| SAST | Bandit bloqueante | `audit/gitlab-bandit-report.json` |
| Detecção de segredos | Gitleaks bloqueante | `audit/gitlab-secret-detection-report.json` |
| Dependências backend | pip-audit bloqueante | `audit/gitlab-pip-audit-report.json` |
| Dependências frontend | npm audit bloqueante para alta/crítica | `audit/gitlab-npm-audit-report.json` |
| Sistema de arquivos | Trivy informativo | `audit/gitlab-trivy-report.json` |

## Política de bloqueio

- O Gitleaks bloqueia a esteira quando identifica segredo fora da lista controlada.
- A lista de exceções contém somente quatro valores sintéticos exatos usados por testes e CI; não aceita diretórios nem arquivos inteiros.
- Bandit, pip-audit e npm audit bloqueiam achados conforme a severidade configurada.
- Trivy publica vulnerabilidades altas e críticas como evidência informativa até existir uma política formal de exceção e prazo.
- Imagens dos verificadores usam versão e digest imutáveis para impedir mudança silenciosa de interface.

## Contrato operacional

- O Trivy recebe a raiz do repositório como alvo único, conforme a interface atual do comando `trivy fs`.
- O Gitleaks estende as regras padrão por `.gitleaks.toml` e mantém `--redact` nos relatórios.
- Os relatórios são publicados mesmo quando o job falha (`artifacts.when: always`).
- Nenhuma exceção pode incluir valor real de credencial, caminho amplo ou regra inteira desativada.

## Próximos passos

1. Definir prazo e fluxo de exceção para tornar Trivy bloqueante.
2. Publicar SBOM CycloneDX no painel de segurança.
3. Revalidar periodicamente os digests das imagens por PR governado.
