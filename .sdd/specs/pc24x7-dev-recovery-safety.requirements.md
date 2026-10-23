# PC24x7 DEV recovery safety

## Acceptance Criteria

- The tool refuses hosts, environments, Compose projects, services, roots, paths, and container cardinalities outside the fixed DEV scope.
- Capture and validation record only sanitized metadata and never read or emit runtime credentials, environment values, container logs, or database contents.
- Image preservation uses deterministic rollback tags and verifies each tag independently before any later deployment can be authorized.
- Rollback requires the exact confirmation phrase, an intact manifest fingerprint, preserved images, and the original ordered Compose inputs.
- The read-only deployment check requires the expected runtime SHA, healthy endpoints, one API container, and a sanitized successful `SELECT 1` result.
- Tests cover negative guards, collision and tamper failures, bounded readiness, liveness contracts, rollback sequencing, and direct script invocation.
- No operation in this increment deploys to DEV or touches TEST, HML, STG, PROD, secrets, networking, or branch protection.

## Migração fechada de fontes legadas — 23/10/2026

O run físico `39988405333` comprovou que o runtime governado ainda referenciava
arquivos do checkout legado pelos labels do Compose. A captura recusou esses
caminhos com `external_path_refused` antes de backup, tags ou deploy.

O manifesto privado passa ao schema 4. Somente o wrapper de cutover público DEV
pode migrar fontes externas, e apenas quando existe um override Compose raiz com
nome allowlisted (`docker-compose.admin-dev.override.yml` ou
`docker-compose.pages-stable.override.yml`) em um único checkout irmão do runtime
governado. Env-files externos precisam estar diretamente nesse mesmo checkout.
Todos são copiados, antes de qualquer mutação do runtime, para snapshots privados
`0600` sob `.reqsys-recovery`; o manifesto contém somente caminho interno, tamanho
e hash. O modo `capture` genérico continua recusando qualquer caminho externo.
