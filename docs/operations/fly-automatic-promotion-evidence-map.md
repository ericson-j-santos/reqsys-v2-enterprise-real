# Mapa de evidências da promoção automática

| Evidência | Fonte | Critério bloqueante |
|---|---|---|
| SHA corrente | Git `origin/main` | precisa coincidir exatamente |
| Estado do app | `flyctl status --json` | máquina mínima e região observável |
| Configuração | `flyctl config show` | campos críticos coerentes |
| Secrets | `flyctl secrets list --json` | nomes obrigatórios implantados |
| Releases | `flyctl releases --json` | coleta auditável |
| Checks | `flyctl checks list --json` | todos os checks observados devem passar |
| Runtime | `validate_public_runtime.py` | endpoints obrigatórios verdes |
| Publicação | `validate_publication_sync.py` | SHA do runtime igual ao SHA alvo |
| Login | `validar_login_multi_ambiente.py` | login/redirect coerentes |
| Produção | BACEN Production Hard Gate | autorização positiva |

Os artifacts não contêm valores de secrets.
