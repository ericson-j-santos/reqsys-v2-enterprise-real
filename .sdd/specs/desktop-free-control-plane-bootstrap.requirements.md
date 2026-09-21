# Desktop PC24x7 — bootstrap governado do runner

## Objetivo

Eliminar o estado em que o Desktop Admin Broker e o watchdog estão instalados, mas não existe GitHub Actions runner registrado para recuperação.

## Requisitos

1. Executar apenas em `DESKTOP-PDQK954` Windows x64.
2. Usar apenas o repositório `ericson-j-santos/reqsys-v2-enterprise-real`.
3. Registrar nome fixo `DESKTOP-PDQK954` com labels adicionais `pc24x7,reqsys-dev`.
4. Baixar somente a versão de runner fixada no código e validar SHA-256 antes da extração.
5. O token de registro deve ser solicitado pelo GitHub CLI autenticado do owner, existir apenas em memória e nunca aparecer em output, logs ou arquivos.
6. O bootstrap pode instalar GitHub CLI por winget quando ausente; autenticação interativa permanece limite legítimo quando necessária.
7. Reutilizar runner já registrado quando o contrato local `.runner + run.cmd + bin\\Runner.Listener.exe` estiver válido.
8. Iniciar `Runner.Listener.exe` e exigir prova local antes de declarar runtime ativo.
9. Reutilizar `desktop_control_plane_watchdog.py` para persistência AtStartup+S4U.
10. Não tocar produção, não reiniciar o host e não aceitar shell, repositório, labels, nome de runner ou token arbitrários.
11. Sucesso terminal exige pickup real posterior de workflow `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
