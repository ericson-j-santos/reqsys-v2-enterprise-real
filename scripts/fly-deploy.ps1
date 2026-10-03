# Fly.io foi aposentado permanentemente em 2026-10-02.
param(
    [ValidateSet("prod", "dev", "staging")]
    [string]$Env = "prod",
    [switch]$SecretsOnly
)

# FLYIO_RETIREMENT_GUARD
throw "Fly.io foi retirado definitivamente em 2026-10-02; deploy, criacao de apps, volumes e secrets estao bloqueados."
