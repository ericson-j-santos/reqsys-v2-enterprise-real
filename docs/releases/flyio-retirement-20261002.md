# Retirada definitiva do Fly.io — 2026-10-02

Decisão explícita do usuário: retirar Fly.io de todas as soluções e ambientes, inclusive como contingência.

Este hotfix bloqueia com condições constantes falsas (`false` ou `false && (...)`) os 53 jobs em 32 workflows que referenciam diretamente operações, credenciais ou workflows reutilizáveis Fly.io. Os contratos existentes de inputs/outputs e o código histórico são preservados para evitar invalidação de callers durante a retirada. Jobs bloqueados não constituem evidência de deploy ou de disponibilidade.

O encerramento definitivo ainda exige revisar chamadas indiretas e pipelines GitLab, remover configurações e scripts legados, migrar consumidores/endpoints e persistência, comprovar backup/restauração e E2E no runtime substituto, revogar tokens e secrets e confirmar o inventário Fly.io vazio. Nenhum app, banco ou volume é apagado por este hotfix.

Validações locais: bootstrap/Command Gateway válidos; gate de incremento autorizou hotfix OPS-GAP-FLY-RETIREMENT; os 32 workflows foram interpretados como YAML e os 53 jobs alterados possuem condição constante falsa.
