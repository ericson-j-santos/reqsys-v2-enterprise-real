# Bootstrap gratuito do control plane no Noteri

## Requisito 1 — host restrito
O launcher e o bootstrap devem falhar fechado fora do host `Noteri`.

## Requisito 2 — reutilização do runner existente
A ativação deve localizar somente um GitHub Actions runner já registrado, comprovado por `.runner`, `run.cmd` e `bin/Runner.Listener.exe`. O bootstrap não registra runner nem recebe token de registro.

## Requisito 3 — falha fechada sem registro
Quando nenhum runner válido existir, o resultado deve ser `runner_registration_required`, sem fallback para RDC, segredo, produção, reboot ou shell genérico.

## Requisito 4 — watchdog governado
Quando o runner existir, o bootstrap deve reutilizar `noteri_control_plane_watchdog.py` com `source_sha` de 40 caracteres e a confirmação do contrato do watchdog.

## Requisito 5 — launcher sem segredo
O launcher CMD deve usar confirmação explícita `ACTIVATE-NOTERI-FREE-CONTROL-PLANE`, que é um guard de intenção e não uma credencial, e não deve aceitar token, senha ou segredo.

## Critérios de aceite (Acceptance Criteria)
1. `ruff` aprova `scripts/activate_noteri_free_control_plane.py`.
2. `tests/test_activate_noteri_free_control_plane.py` aprova host pinning, contrato do runner, integração com watchdog e ausência de entradas secretas.
3. A confirmação explícita do launcher é validada positivamente pelo teste, sem ser confundida com segredo.
4. Ausência de runner previamente registrado permanece fail-closed como `runner_registration_required`.
5. A implementação preserva `rdc_required=false`, `production_touched=false` e `secrets_read=false`.
6. O SDD gate reconhece esta especificação e o teste mapeado no HEAD exato do PR.
7. O Pre-PR Readiness deve retornar `READY_FOR_PR=passed` contra a `main` corrente.
