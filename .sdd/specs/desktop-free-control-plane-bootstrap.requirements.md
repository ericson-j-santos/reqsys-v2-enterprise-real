# Desktop PC24x7 — bootstrap governado do runner

## Objetivo

Eliminar o estado em que o Desktop Admin Broker e o watchdog estão instalados, mas não existe GitHub Actions runner registrado para recuperação.

## Requisitos

1. Executar apenas em `DESKTOP-PDQK954` Windows x64.
2. Usar apenas o repositório `ericson-j-santos/reqsys-v2-enterprise-real`.
3. Registrar nome fixo `DESKTOP-PDQK954` com labels adicionais `pc24x7,reqsys-dev`.
4. Baixar somente a versão de runner fixada no código e validar SHA-256 antes da extração.
5. O token de registro deve ser solicitado pelo GitHub CLI autenticado do owner, existir apenas em memória e nunca aparecer em output, logs ou arquivos.
6. O bootstrap pode instalar GitHub CLI por winget quando ausente; autenticação interativa permanece limite legítimo na execução local, mas o modo `--non-interactive-auth` usado pelo broker deve falhar fechado antes de login ou refresh interativo.
7. Reutilizar runner já registrado quando o contrato local `.runner + run.cmd + bin\\Runner.Listener.exe` estiver válido.
8. Iniciar `Runner.Listener.exe` e exigir prova local e registro `online` no GitHub antes de declarar runtime ativo.
8.1. A prova local deve pertencer ao executável `bin\\Runner.Listener.exe` do `runner_home` governado; listener de outro runner ou identidade não verificável deve falhar fechado.
8.2. Se o runner governado estiver localmente ativo, registrado com labels corretas, porém `offline` no GitHub, o bootstrap pode executar exatamente um reinício controlado desse listener e revalidar o registro.
8.3. O reinício por estado `offline` não se aplica a registro ausente, labels divergentes ou processo não verificável.
9. Reutilizar `desktop_control_plane_watchdog.py` para persistência AtStartup+S4U.
10. Não tocar produção, não reiniciar o host e não aceitar shell, repositório, labels, nome de runner ou token arbitrários.
11. Sucesso terminal exige pickup real posterior de workflow `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.

## Critérios de aceite

- O bootstrap falha fechado fora de `DESKTOP-PDQK954`.
- O runner oficial é aceito somente após SHA-256 corresponder ao valor fixado.
- O token de registro não é persistido, não é logado e é descartado após o uso.
- O runner é registrado com nome `DESKTOP-PDQK954` e labels `pc24x7,reqsys-dev`.
- `Runner.Listener.exe` deve estar ativo antes de `runtime_active`.
- A API do GitHub deve retornar exatamente o runner `DESKTOP-PDQK954` com `status=online`.
- As labels `self-hosted`, `Windows`, `X64`, `pc24x7` e `reqsys-dev` são obrigatórias; divergência produz estado explícito e falha fechada.
- Ausência no registro, status offline e processo local ausente devem produzir estados distintos.
- Um listener local de outro runner não deve satisfazer a prova do `DESKTOP-PDQK954`.
- O estado `offline` com registro/labels válidos permite no máximo um reinício do listener governado por invocação antes de falhar fechado.
- O watchdog do Desktop é instalado ou fica explicitamente `activation_pending` sem falso positivo.
- Nenhum reboot, produção ou destino arbitrário é tocado.
- A conclusão operacional exige pickup real de workflow self-hosted PC24x7.
