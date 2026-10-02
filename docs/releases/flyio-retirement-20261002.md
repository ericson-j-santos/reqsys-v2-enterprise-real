# Retirada definitiva do Fly.io — 2026-10-02

Decisão explícita do usuário: retirar Fly.io de todas as soluções e ambientes, inclusive como contingência.

## Controles no repositório

O primeiro hotfix bloqueou com condições constantes falsas (`false` ou `false && (...)`) 53 jobs em 32 workflows que referenciavam diretamente operações, credenciais ou workflows reutilizáveis Fly.io. Esta finalização encontrou e bloqueou mais 20 jobs em 19 workflows que ainda consumiam URLs `fly.dev` sem chamar `flyctl`. Os contratos históricos de inputs e outputs permanecem apenas para compatibilidade; job ignorado não é evidência de deploy ou disponibilidade.

Na edição GitLab, os includes de deploy e OCR staging foram removidos, os arquivos de CI correspondentes foram excluídos, os Review Apps foram retirados e o provisionamento de token do provedor deixou de existir. O pipeline semântico e o gate de evidência agora conservam somente a baseline provider-neutral. O validador GitLab falha se esses includes, arquivos, jobs ou referências executáveis forem reintroduzidos.

O endpoint de deploy operacional do backend foi aposentado: o catálogo informa `RETIRADO` e validação/execução respondem HTTP 410 sem despachar GitHub Actions. A integração GovBI deixou de usar fallback Fly.io e exige `GOVBI_BASE_URL` explícita; hosts `fly.dev` e `fly.io` são rejeitados.

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

## Pendências que impedem declarar encerramento corporativo integral

- publicar e integrar esta finalização, preparada sobre a `main` em `c45ba453dbbd6978c0dda34838568e9db282cefe`;
- autenticar no GitHub para remover cópias inertes de secrets/variables e revalidar ReqSys Java e ReqSys Platform;
- publicar os bloqueios já preparados para `main` e `develop` do GovBI IA;
- publicar a neutralização já preparada de `scripts/deploy.ps1` no MCMV Rural e tratar refs antigas manualmente despacháveis do ReqSys VSCode Agent;
- revisar no painel Fly.io a fatura corrente e o método de pagamento. A organização segue `CURRENT`, `billable=true`, `paidPlan=true` e com cartão cadastrado, embora apps e add-ons estejam zerados.

Validações locais desta finalização no SHA-base acima: 575 workflows interpretados como YAML; 33 testes dos gates Fly/GitLab/lifecycle, 64 testes backend focados e seis testes do runtime de reprocessamento verdes; validador GitLab, Ruff focado e `git diff --check` aprovados.
