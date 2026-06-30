# Runbook — Publicar repositório independente do Ollama Local Gateway

## Objetivo

Padronizar a criação e publicação do repositório independente `ericson-j-santos/reqsys-ollama-local-gateway`, mantendo o ReqSys como produto principal e o gateway como provider local governado.

## Estado atual evidenciado

- Repositório: `ericson-j-santos/reqsys-ollama-local-gateway` — **existe e acessível**
- Versão publicada alvo: `0.2.0` com `POST /v1/chat`
- Issue relacionada: `#95`
- Provider ReqSys: `ollama_gateway` integrado ao Codex governado

## Decisão arquitetural

O gateway independente não substitui o Codex Local/Online do ReqSys. Ele deve atuar como provider local via HTTP para permitir uso de modelos Ollama em ambiente controlado.

## Publicação automatizada

```bash
bash scripts/sincronizar_ollama_gateway_repo.sh
```

O script valida o bootstrap (`pytest` + `ruff`), publica no repositório externo e abre branch para PR.

## Comandos sugeridos após merge no repositório externo

```bash
git clone https://github.com/ericson-j-santos/reqsys-ollama-local-gateway.git
cd reqsys-ollama-local-gateway

git checkout -b bootstrap/gateway-inicial
# copiar/adaptar pacote independente gerado pelo ReqSys
python -m pytest -q
ruff check .

git add .
git commit -m "feat: bootstrap do ReqSys Ollama Local Gateway"
git push -u origin bootstrap/gateway-inicial
```

Depois, abrir PR para `main` no repositório independente.

## Próximo passo após publicação

1. Vincular o PR do novo repositório à issue `#95` do ReqSys.
2. Atualizar o PR `#96` com o link do repositório independente.
3. Validar consumo do gateway via provider `ollama_gateway` no ReqSys.
4. Manter isolamento arquitetural: o ReqSys consome o gateway por API; não duplicar produto dentro do monólito.

## Status operacional

Repositório externo criado. Use `scripts/sincronizar_ollama_gateway_repo.sh` para publicar atualizações. O ReqSys consome o gateway via provider `ollama_gateway`.