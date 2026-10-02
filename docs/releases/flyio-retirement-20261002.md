# Retirada definitiva do Fly.io — 2026-10-02

Decisão explícita do usuário: retirar Fly.io de todas as soluções e ambientes, inclusive como contingência.

## Controles no repositório

O primeiro hotfix bloqueou com condições constantes falsas (`false` ou `false && (...)`) 53 jobs em 32 workflows que referenciavam diretamente operações, credenciais ou workflows reutilizáveis Fly.io. Esta finalização encontrou e bloqueou mais 20 jobs em 19 workflows que ainda consumiam URLs `fly.dev` sem chamar `flyctl`. Os contratos históricos de inputs e outputs permanecem apenas para compatibilidade; job ignorado não é evidência de deploy ou disponibilidade.

Na edição GitLab, os includes de deploy e OCR staging foram removidos, os arquivos de CI correspondentes foram excluídos, os Review Apps foram retirados e o provisionamento de token do provedor deixou de existir. O pipeline semântico e o gate de evidência agora conservam somente a baseline provider-neutral. O validador GitLab falha se esses includes, arquivos, jobs ou referências executáveis forem reintroduzidos.

O endpoint de deploy operacional do backend foi aposentado: o catálogo informa `RETIRADO` e validação/execução respondem HTTP 410 sem despachar GitHub Actions. A integração GovBI deixou de usar fallback Fly.io e exige `GOVBI_BASE_URL` explícita; hosts `fly.dev` e `fly.io` são rejeitados.

Nos workflows alterados, 53 referências a actions de terceiros foram fixadas por SHA imutável. O runtime também deixou de consumir `FLY_IMAGE_REF` como fallback de identificação de build: sem `GITHUB_SHA`, responde `unknown`.

## Encerramento remoto confirmado

Antes da exclusão foram inventariados 14 apps, 17 Machines e seis volumes persistentes. Os bancos foram exportados e validados; em seguida:

- os 14 apps foram destruídos e o inventário autenticado passou a zero;
- os 14 hostnames antigos deixaram de resolver em DNS;
- os dois buckets Tigris `reqsys-backups-dev` e `reqsys-backups-dev-v5` foram destruídos;
- Managed Postgres, Redis, Kubernetes e os 12 tipos de add-on consultados ficaram com inventário zero;
- dez tokens de organização ativos foram revogados; os 11 registros históricos estão revogados;
- sete segredos Fly no Key Vault `kv-reqsys-ccp` foram removidos e purgados;
- a variável GitLab `FLY_API_TOKEN_SOURCE` foi removida e não restou variável com `FLY` no projeto.

## Backup e restauração

O conjunto canônico de recuperação está em `C:\Users\Windows\Documents\Codex\2026-10-02\flyio-retirement-final`, com segunda cópia em `C:\Users\Windows\OneDrive\ReqSys\Backups\flyio-retirement-20261002`. São 12 envelopes Fernet autenticados; a chave permanece no Key Vault sob `flyio-retirement-backup-key-20261002`.

Foram verificados quatro bancos SQLite com `quick_check`, dois bundles PostgreSQL com checksums internos e restauração dos bancos de aplicação em PostgreSQL 17. Os dumps `repmgr` têm listagem e checksum válidos, mas a restauração integral requer a extensão `repmgr`. Manifest e envelopes das duas cópias são byte a byte idênticos. Os arquivos temporários em texto claro permanecem protegidos por EFS até a limpeza local.

## Atualização das frentes correlatas

- a auditoria automatizada percorreu 290 repositórios GitHub nos escopos disponíveis. Os seis resíduos Fly.io identificados foram removidos: `FLY_API_TOKEN` e `CCP_AZURE_CLIENT_ID_FLY_GOVERNED_COMMAND` no ReqSys, `FLY_API_TOKEN` e `FLY_APP_NAME` no environment `development`, além de `FLY_API_TOKEN` em ReqSys Java e GovBI IA. A reconsulta dos mesmos escopos não retornou referência Fly.io;
- MCMV Rural: PR [#1](https://github.com/ericson-j-santos/mcmv-rural-painel/pull/1) integrada à `main` (`aa8de4ce5a0903586af6215f662bba3a2b26a306`);
- GovBI IA: PR [#5](https://github.com/ericson-j-santos/govbi-ia/pull/5) integrada à `develop` (`848c25b50fbab1be58e3f41c3f948fe0910f3ab7`) e PR [#6](https://github.com/ericson-j-santos/govbi-ia/pull/6) integrada à `main` (`eec6ea20e4f543cc78dcd1ff550ad8ad14e75fa8`); os jobs de deploy permanecem fail-closed;
- Cadastra PF: PR [#1](https://github.com/ericson-j-santos/cadastra-pf-siopi/pull/1) integrada à branch padrão (`66bd1d24420f58a5cc491f943655cff06a0a515b`);
- ReqSys Java e ReqSys Platform: os caminhos de deploy Fly.io permanecem bloqueados por condição constante falsa. As referências históricas preservadas não equivalem a capacidade operacional;
- ReqSys VSCode Agent: o workflow `Legacy Fly.io Public Deploy` foi desabilitado manualmente e um novo despacho foi rejeitado. O workflow `Fly.io Rollback Readiness` e tooling histórico ainda exigem retirada;
- Power BI e Power Platform ALM têm mudanças preparadas nas PRs [#19](https://github.com/ericson-j-santos/painel-powerbi/pull/19) e [#10](https://github.com/ericson-j-santos/reqsys-powerplatform-alm/pull/10), ainda sem integração porque os runners Noteri dedicados estão indisponíveis.

## Pendências que impedem declarar encerramento corporativo integral

- concluir os checks obrigatórios, inclusive E2E responsivo, e integrar a PR ReqSys [#2191](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/2191);
- integrar a PR Power BI [#19](https://github.com/ericson-j-santos/painel-powerbi/pull/19), cujos dois checks aguardam os runners repo-scoped `Noteri-PainelPowerBI` e `Noteri-PainelPowerBI-Guard`;
- integrar a PR Power Platform ALM [#10](https://github.com/ericson-j-santos/reqsys-powerplatform-alm/pull/10), cujo runner anterior foi removido, e validar/desativar os fluxos importados no ambiente Power Automate;
- retirar o workflow ainda ativo `Fly.io Rollback Readiness` e as referências de contingência remanescentes no ReqSys VSCode Agent;
- ampliar temporariamente a autenticação GitHub com o escopo `codespace` apenas para auditar/remover eventuais secrets Fly.io no escopo de usuário Codespaces;
- revisar e encerrar no Fly.io a conta/organização, a fatura corrente e o método de pagamento. O inventário de recursos zerado não confirma cancelamento da conta nem encerramento de cobrança.

Validações desta finalização: 575 workflows interpretados como YAML; 64 testes backend focados, 47 testes root focados, 14 testes do contrato Teams/Azure, 15 testes focados pós-rebase e 42 testes do runtime/monitoramento aprovados; validador GitLab, Ruff focado e `git diff --check` aprovados. O gate remoto `READY_FOR_PR` passou no head anterior à atualização deste registro; todos os checks serão exigidos novamente no head final antes do merge.
