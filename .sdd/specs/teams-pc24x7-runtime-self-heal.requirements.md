# Teams PC24x7 runtime self-heal — requisitos

## Contexto

O bootstrap S2S da Central IA/Teams DEV exige que o runtime público PC24x7 execute exatamente o SHA do workflow. A validação fail-closed já existe, mas uma divergência de SHA interrompe o fluxo sem tentar reconciliar o checkout persistente que alimenta o runtime.

## Critérios de aceite

1. A reconciliação executa somente no host `DESKTOP-PDQK954`, ambiente DEV e projeto Compose `wt-pc24x7-piloto`.
2. O runtime é descoberto pela API DEV publicada na porta 8210 e pelos labels reais do Docker Compose; caminhos arbitrários não são aceitos.
3. O checkout persistente precisa apontar para `ericson-j-santos/reqsys-v2-enterprise-real` e não pode possuir alterações rastreadas locais.
4. O SHA esperado precisa pertencer ao histórico atual de `origin/main`.
5. A atualização local aceita somente `git merge --ff-only`; reset forçado, force-push e rebase não fazem parte da solução.
6. Arquivos locais não rastreados, inclusive o override administrativo DEV, são preservados.
7. O segredo existente do Teams Bot é recuperado do Azure Key Vault via identidade OIDC já governada e nunca é incluído em evidência, log sanitizado ou repositório.
8. A recriação reutiliza `recreate_cofre_dev_pc24x7.py`, o override administrativo observado no runtime e `config/pc24x7-teams-bot-runtime.override.yml`.
9. Somente a API DEV é recriada; HML/STG/PROD não são tocados.
10. A reconciliação só conclui quando `/api/runtime/build-info` reportar exatamente o SHA esperado e `/api/runtime/health` responder com sucesso.
11. O workflow `pc24x7-teams-token-bootstrap.yml` executa a reconciliação antes de validar/provisionar o token S2S.
12. Falha na reconciliação bloqueia o bootstrap antes da mutação do token.
13. A execução publica artifact sanitizado com correlation_id, SHA anterior/final e estado do runtime, sem valores sensíveis.
14. O workflow self-hosted precisa permanecer explicitamente allowlisted em `.github/self-hosted-runner-policy.json`, coberto pelo ADR-046 e pelo teste de governança do repositório.
