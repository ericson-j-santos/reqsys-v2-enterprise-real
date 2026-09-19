# Cofre — gate DEV sem runner self-hosted nem login local

## Objetivo

Eliminar ações humanas recorrentes do **Cofre Runtime Evidence Gate** no PC24x7 DEV.

O gate deve conseguir provar o ciclo completo no SHA corrente usando apenas:
- GitHub-hosted runner;
- HTTPS para a API DEV;
- credencial já governada do Cofre;
- restart do próprio container via política Docker `restart: unless-stopped`.

## Requisitos

1. O workflow oficial roda em `ubuntu-latest`; não exige self-hosted runner.
2. O controle remoto é exposto somente pelo runtime Cofre DEV e exige a mesma autenticação governada `cofre:runtime_evidence`.
3. O overlay PC24x7 define explicitamente:
   - `REQSYS_RUNTIME_ENVIRONMENT=dev`;
   - `COFRE_RUNTIME_SELF_RESTART_ENABLED=1`.
4. O restart falha fechado fora de DEV, quando a flag está ausente/desligada ou quando `GITHUB_SHA != expected_sha`.
5. A solicitação exige confirmação literal `RESTART-COFRE-DEV-RUNTIME`.
6. `X-Correlation-Id` é obrigatório e o replay do mesmo correlation_id + SHA é idempotente.
7. Antes de reiniciar, o workflow lê `environment`, `runtime_sha`, `boot_id` e a flag de habilitação.
8. O restart encerra somente PID 1 do container da API; nenhum Docker socket ou credencial do host é exposto.
9. A política `restart: unless-stopped` deve trazer o container de volta.
10. Depois do restart, o workflow exige:
    - mesmo SHA;
    - novo `boot_id`;
    - readiness público;
    - segredo persistido;
    - cleanup completo.
11. Evidência publicada nunca contém JWT, token do Cofre ou valores de segredo.
12. `production_touched=false` deve permanecer explícito.
13. HML/STG/PROD permanecem fora do escopo.
14. Fly.io permanece bloqueado como runtime do Cofre DEV.
15. A mudança não depende de aprovação de `Administration: write` em GitHub App e não registra GitHub Actions runner.

## Controles negativos

- sem autenticação => 401;
- ambiente diferente de dev => 403;
- flag desligada => 409;
- SHA divergente => 409;
- confirmação incorreta => 422;
- boot_id não muda => gate falha;
- runtime volta em outro SHA => gate falha;
- replay da mesma solicitação => não agenda segundo restart.

## Critério de conclusão

A implementação está pronta para integração quando testes unitários/contrato, YAML, SDD, Pre-PR Readiness e controles negativos estiverem verdes. A conclusão operacional da #1760 exige, após integração e publicação deste SHA no DEV, um novo run oficial do Cofre verde no SHA então vigente.
