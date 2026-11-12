# Reativação segura do relatório de Trilhas A–E sem Fly.io/Docker

## Problema
Na main do ReqSys `bf1f637eb945e70b27d1b4ea298105ee925aad77`, `.github/workflows/trilhas-padrao-ouro.yml` e `.github/workflows/trilha-a-runtime-publico.yml` contêm `if: ${{ false }}`. O validador `scripts/runtime_public_validator.py` foi aposentado com o Fly.io. O DEV atual está declarado no manifesto `infra/public-access-urls.json`.

## Escopo do reparo
Trocar a chamada do validador aposentado por verificação estática do manifesto atual: GitHub Pages, localizador com assinatura Ed25519, transporte Cloudflare e PC24x7. Reativar workflows de relatório sem Docker, apt/ODBC, deploy, rede ou instalação. HML e PROD permanecem sem promoção.

## Critérios de aceite (Acceptance Criteria)
1. Configuração atual passa, mas retorna `passed_with_warnings` e `physical_e2e_verified=false`.
2. Dez testes positivos/negativos cobrem manifesto ausente, JSON inválido, alvo Fly, gateway externo, assinatura ausente, HML promovida, entrada duplicada e URL insegura.
3. Trilha A produz relatório com erros bloqueantes para configuração inválida, e o consolidador rejeita status desconhecidos, saída vazia e erros.
4. Workflow Trilha A e A–E são realmente executados em PR, produzem relatório/artefatos, sem Fly.io, Docker, ODBC, dependências backend completas ou comandos no host.
5. O workflow demonstra os testes e não declara recuperação física apenas com CI verde. Retorno `passed_with_warnings` é explícito no relatório, sem falso `healthy`.
6. SHA da branch, `READY_FOR_PR`, Validator, origem do reparo e custo incremental R$0 precisam de evidência antes de PR draft. Merge e testes físicos requerem autorização própria.

## Próximas entregas e responsáveis
P1: reativar consolidado estático (Engineering Control Plane); P2: validar PR/CI e proveniência; P3: observar saúde PC24x7 e assinatura externa (Runtime Platform); P4: integrar com autorização PR #3143 Windows, validar Noteri; P5: PR #3141, lease/recibos independentes e E2E dois hosts.

Origem: correção assistida em chat, sem Builder externo ou digest autenticado; issue #3145, regras main `58dcd4200f412a866278027ba9e433439a03f3b3`. Não declarar homologação física.
