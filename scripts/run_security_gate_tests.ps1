$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (Test-Path "backend") {
    Set-Location "backend"
}

python -m pytest tests/test_security_production_gates_individual.py -v --tb=short
python -m pytest tests/test_security_cors_individual.py -v --tb=short
python -m pytest tests/test_security_auth_jwt_individual.py -v --tb=short
