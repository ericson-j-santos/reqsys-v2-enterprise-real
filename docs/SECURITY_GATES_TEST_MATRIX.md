# Matriz de testes — PR #18 — Production Security Gates

## Objetivo

Garantir que cada gate de produção tenha teste separado, executável de forma individual e rastreável no CI.

## Gates cobertos

| Gate | Arquivo de teste | Critério |
|---|---|---|
| `JWT_SECRET` fraco | `test_security_production_gates_individual.py` | Bloqueia boot em produção. |
| `CORS_ORIGINS=*` | `test_security_cors_individual.py` | Bloqueia wildcard em produção. |
| `JWT_ISSUER` ausente | `test_security_production_gates_individual.py` | Bloqueia JWT sem emissor esperado. |
| `JWT_AUDIENCE` ausente | `test_security_production_gates_individual.py` | Bloqueia JWT sem audiência esperada. |
| `ALLOW_DEMO_LOGIN=true` | `test_security_production_gates_individual.py` | Bloqueia login demo em produção. |
| `JWT_EXP_MINUTES <= 0` | `test_security_production_gates_individual.py` | Bloqueia TTL inválido. |
| TTL explícito `0` | `test_security_auth_jwt_individual.py` | Não faz fallback indevido para default. |
| `issuer` inválido | `test_security_auth_jwt_individual.py` | Rejeita token assinado, mas de emissor incorreto. |
| `audience` inválida | `test_security_auth_jwt_individual.py` | Rejeita token assinado, mas para audiência incorreta. |
| Token expirado | `test_security_auth_jwt_individual.py` | Rejeita token vencido. |

## Execução individual

```bash
cd backend
python -m pytest tests/test_security_production_gates_individual.py -v --tb=short
python -m pytest tests/test_security_cors_individual.py -v --tb=short
python -m pytest tests/test_security_auth_jwt_individual.py -v --tb=short
```

## Execução consolidada

```bash
bash scripts/run_security_gate_tests.sh
```

No Windows:

```powershell
.\scripts\run_security_gate_tests.ps1
```

## Critério de aceite

O PR só deve ser considerado pronto para merge quando todos os testes acima passarem isoladamente e em conjunto com a suíte completa do backend.
