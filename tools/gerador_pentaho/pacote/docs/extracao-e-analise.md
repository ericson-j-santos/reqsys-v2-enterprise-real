# Extração e análise da imagem

## Elementos legíveis com alta confiança

Fluxo principal observado:

1. `Generate Rows`
2. `monta JSON Auth`
3. `SIMTR Auth`
4. `OK?`
5. `JSON auth`
6. `Auth OK?`
7. `Join`, alimentado também por `Query JSON` → `Tentativas`
8. `monta JSON API`
9. `REST API cria Dossie`
10. `Extrair ID Dossie`
11. `Resultado`
12. `tem dossie?`
13. sucesso: `gravar sucesso` → `Write to log 2`
14. falha: `gravar falha` → `Write to log falha`

Desvios observados: `OK?` → `Faz Nada 2`; `Auth OK?` → `Faz Nada 3` → `Write to log 4`.

## Inferências — exigem confirmação no `.ktr`

- `SIMTR Auth` aparenta ser uma chamada REST de autenticação.
- `JSON auth` aparenta extrair o token retornado.
- `Tentativas` aparenta controlar repetição, mas a imagem não comprova backoff ou limite.
- `Resultado` aparenta normalizar a resposta antes da decisão final.
- Não é possível confirmar URL, método, headers, consultas, campos, timeouts, política de retry ou persistência.

## Riscos do desenho observado

| Semáforo | Risco | Tratamento na versão de treino |
|---|---|---|
| 🔴 | Falhas silenciosas em `Faz Nada` | estado final explícito e evidência JSON |
| 🔴 | Possível segredo no JSON/log | segredo somente em runtime; logs sem token |
| 🟠 | Retentativa sem política visível | limite, timeout e retry apenas transitório |
| 🟠 | Nomes misturam tecnologia e domínio | linguagem ubíqua em português |
| 🟠 | Idempotência não evidenciada | SHA-256 por demanda/data |
| 🟡 | Contratos não visíveis | validação mínima de entrada e resposta |

## Limite da sanitização

A foto não permite extrair configurações internas. Assim, a sanitização foi feita por **substituição integral**, não por mascaramento parcial: todos os dados operacionais foram recriados como valores sintéticos.

