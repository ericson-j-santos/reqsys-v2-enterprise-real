# GitLab DevSecOps Baseline

## Objetivo

Definir a linha de base de DevSecOps da ReqSys v2 Enterprise GitLab Edition.

## Capacidades alvo

| Capacidade | Estado inicial | Artifact alvo |
|---|---|---|
| SAST | placeholder governado | `gl-sast-report.json` |
| Secret Detection | placeholder governado | `gl-secret-detection-report.json` |
| Dependency Scanning | placeholder governado | `gl-dependency-scanning-report.json` |
| Container Scanning | placeholder governado | `gl-container-scanning-report.json` |
| SBOM | placeholder governado | `gl-sbom-report.cdx.json` |

## Política de bloqueio futura

Quando os scanners reais forem habilitados no GitLab:

- bloquear merge com segredo exposto;
- bloquear merge com vulnerabilidade crítica/alta sem exceção aprovada;
- publicar artifacts de evidência em todos os pipelines de segurança;
- exigir revisão coordenadora para exceções;
- manter histórico auditável de decisões.

## Escopo deste incremento

Este incremento não ativa scanners reais, secrets, registry ou produção. Ele cria a estrutura governada para permitir ativação segura quando o projeto estiver em GitLab com runners e variáveis configuradas.

## Próximos passos

1. Habilitar GitLab SAST template.
2. Habilitar Secret Detection real.
3. Configurar Dependency Scanning conforme stack.
4. Integrar Container Scanning após registry.
5. Publicar SBOM e security dashboard.
