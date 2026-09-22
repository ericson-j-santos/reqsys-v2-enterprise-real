# ReqSys Codex Online

Aplicação online estática para operar o fluxo de análise governada de código e gerar payloads compatíveis com ReqSys.

## Objetivo

Permitir uso totalmente online via GitHub Pages, mantendo o modelo seguro por padrão:

- sem credenciais no frontend;
- modo demonstração seguro;
- backend real opcional;
- geração de `correlation_id`;
- payload rastreável para ReqSys;
- validação por GitHub Actions.

## Uso local (VS Code + Ollama)

Para codificação gratuita no editor:

```bash
bash scripts/iniciar_codex_local.sh
cp infra/codex-local/continue/config.yaml ~/.continue/config.yaml
```

Runbook completo: `docs/runbooks/codex-vscode-local-inicio-rapido.md`

Tela integrada no ReqSys: `http://127.0.0.1:5173/codex`

## Publicação

O workflow `.github/workflows/codex-local-online.yml` valida o artefato em Pull Request e publica no GitHub Pages quando a alteração chegar à `main` ou quando o workflow for executado manualmente.

URL esperada após publicação:

```text
https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/
```

## Integração real com backend

Para usar modelo real, publique um backend seguro e informe o endpoint no campo da aplicação. O endpoint deve aceitar:

```json
{
  "correlation_id": "codex-...",
  "prompt": "...",
  "source": "reqsys-codex-online"
}
```

O backend deve aplicar autenticação, CORS restrito, rate limit, auditoria e bloqueio de dados sensíveis.
