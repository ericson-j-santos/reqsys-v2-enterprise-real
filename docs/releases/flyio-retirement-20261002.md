# Retirada definitiva do Fly.io — 2026-10-02

Decisão explícita do usuário: retirar Fly.io de todas as soluções e ambientes, inclusive como contingência.

## Controles no repositório

O primeiro hotfix bloqueou com condições constantes falsas (`false` ou `false && (...)`) 53 jobs em 32 workflows que referenciavam diretamente operações, credenciais ou workflows reutilizáveis Fly.io. A auditoria ampliada elevou o total para 96 jobs permanentemente bloqueados em 60 workflows, incluindo consumidores indiretos via `env`, inputs e manifestos legados. Os contratos históricos de inputs e outputs permanecem apenas para compatibilidade; job ignorado não é evidência de deploy ou disponibilidade.

Na edição GitLab, os includes de deploy e OCR staging foram removidos, os arquivos de CI correspondentes foram excluídos, os Review Apps foram retirados e o provisionamento de token do provedor deixou de existir. O pipeline semântico e o gate de evidência agora conservam somente a baseline provider-neutral. O validador GitLab falha se esses includes, arquivos, jobs ou referências executáveis forem reintroduzidos.

O endpoint de deploy operacional do backend foi aposentado: o catálogo informa `RETIRADO` e validação/execução respondem HTTP 410 sem despachar GitHub Actions. A integração GovBI deixou de usar fallback Fly.io e exige `GOVBI_BASE_URL` explícita; hosts `fly.dev` e `fly.io` são rejeitados.

Os 13 manifestos `fly*.toml`, os dois `Dockerfile.fly` e os dois entrypoints `fly_boot.sh` foram removidos; o benchmark OCR passou a usar `backend/Dockerfile`. Catálogo de credenciais, lifecycle e ativos de backup passaram a marcar Fly.io como histórico, desabilitado e sem bindings. Frontend, launchpad, Teams e Codex Online deixaram de expor links Fly; scripts de rede e consolidadores exigem destinos explícitos e recusam `fly.dev`/`fly.io` antes de qualquer I/O externo.

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
- ReqSys Java: a `main` está em `7d916736592c877de75f8921069e5b833fdd46d3`, sem manifesto Fly; o build passou e o job de deploy ficou `skipped`. Duas branches antigas totalmente integradas foram excluídas. A feature com 12 commits exclusivos foi preservada e recebeu a PR [#4](https://github.com/ericson-j-santos/reqsys-java-platform/pull/4), cujo head remove Fly, mas os checks não relacionados ainda estão vermelhos e impedem o merge sem bypass. ReqSys Platform: a `main` está em `f588435ef127faed1bd940de75523d0ba661bc58`, sem manifesto/smoke Fly; o workflow está desabilitado e o job também usa condição constante falsa;
- ReqSys VSCode Agent: a PR [#17](https://github.com/ericson-j-santos/reqsys-vscode-agent/pull/17) foi integrada à `main` (`666bb28f0d85cee2847783f168b5b0365134c4f7`); ela remove deploy/rollback, exclui runbooks e tooling Fly.io, renomeia o smoke provider-neutral e faz CLI/monitor recusarem o provedor;
- Power BI: a PR [#19](https://github.com/ericson-j-santos/painel-powerbi/pull/19) foi integrada em `a0962ddd8bcd6c6742379af12dcd3e876e771163`; 398 testes locais, CI da PR e CI pós-merge passaram;
- Power Platform ALM: após uma correção concorrente executar uma importação real em Test pela PR [#11](https://github.com/ericson-j-santos/reqsys-powerplatform-alm/pull/11), a PR fail-closed [#12](https://github.com/ericson-j-santos/reqsys-powerplatform-alm/pull/12) foi integrada em `2875fbd3134345374c564a86307c9df3f46df44b`. O gate de aposentadoria passou e `build-and-deploy` ficou `skipped` em zero segundo, sem steps. O bloqueio impede recorrência, mas não desfaz a importação anterior no ambiente Test.

## Pendências que impedem declarar encerramento corporativo integral

- integrar a PR de fechamento dos resíduos descobertos após a integração da PR ReqSys [#2191](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/2191), já incorporada à `main` em `abe31b0f3bc4b9f078c348528960b5a95734b3a7`;
- integrar a PR Java [#4](https://github.com/ericson-j-santos/reqsys-java-platform/pull/4) quando os gates Maven/Trivy preexistentes estiverem verdes; a branch-base preservada ainda contém o manifesto histórico, embora não possa executar deploy fora da `main`;
- avaliar no ambiente Power Platform Test se a importação registrada no run da PR #11 requer rollback funcional; nenhuma reversão foi presumida ou executada;
- ampliar temporariamente a autenticação GitHub com o escopo `codespace` apenas para auditar/remover eventuais secrets Fly.io no escopo de usuário Codespaces;
- revisar e encerrar no Fly.io a conta/organização, a fatura corrente e o método de pagamento. O inventário de recursos zerado não confirma cancelamento da conta nem encerramento de cobrança.

Validações desta finalização no estado pós-merge: 575 workflows interpretados como YAML e sete JSON alterados validados; 320 testes raiz e 183 testes backend focados aprovados; 321 testes frontend e sete testes Node da política de URL aprovados; build frontend concluído com 964 módulos; Ruff canônico aprovado nos 125 arquivos Python do diff; todas as actions externas dos 25 workflows alterados fixadas por SHA; `git diff --check` aprovado; gate SDD aprovado para 142 arquivos funcionais. A suíte raiz ampliada aprovou 3.361 testes e expôs uma regressão Fly no gate DEV, corrigida e revalidada; as dez falhas restantes são baselines alheias à retirada (portabilidade Windows, exceção regulatória expirada, tempo, dependência de runtime local e manifesto de testes). Todos os checks remotos serão exigidos novamente no head final antes do merge.
