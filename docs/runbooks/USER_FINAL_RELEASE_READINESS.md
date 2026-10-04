# Readiness de liberação para usuário final

## Objetivo

Definir um checklist de **evidência**, não de intenção, para acesso controlado, beta operacional e produção.

## Como usar

Para cada item, registrar a evidência atual correspondente (run, artifact, endpoint/readback, teste, SHA ou decisão governada). Item sem evidência atual permanece **pendente**, ainda que a funcionalidade exista no código.

## 1. Acesso e identidade

- Login real ou modo explicitamente autorizado para o ambiente.
- Logout e expiração de sessão validados.
- Rotas privadas bloqueiam acesso anônimo.
- Permissões server-side comprovadas para perfis aplicáveis.
- Redirecionamento pós-login preserva apenas destinos internos seguros.

## 2. Navegação e experiência

- Entrada canônica clara.
- Catálogo de navegação sem rotas órfãs/bloqueios ReqSys 360.
- Telas críticas cobertas por evidência E2E.
- Responsividade desktop/mobile validada.
- Acessibilidade e linguagem simples sem regressões bloqueantes.

## 3. Jornada de requisitos

- Criar requisito e ler por caminho independente.
- Atualizar/consultar respeitando autorização.
- Identificador e `correlation_id` preservados.
- Rastreabilidade para trabalho/entrega/evidência quando aplicável.
- Replay/idempotência validados em operações assíncronas ou integradas.

## 4. Operação

- Monitoramento operacional apresenta estado técnico corrente.
- Falhas não são convertidas em falso verde.
- Incidentes/erros possuem evidência sanitizada.
- Runbook aponta diagnóstico e recuperação segura.
- Runtime/serviços críticos possuem health/readiness aplicáveis.

## 5. Análise e indicadores

- Indicadores possuem fonte e regra.
- Drill-down preserva contexto.
- Dados simulados/estáticos estão identificados como tal.
- GovBI/IA não promove fallback a resultado real.
- Query Intelligence não é confundida com execução SQL/performance real.

## 6. Segurança

- Segredos não aparecem em logs, artifacts ou respostas.
- CORS/JWT/auth atendem ao ambiente alvo.
- Scanners/gates obrigatórios verdes no HEAD atual.
- Fluxos administrativos exigem autorização adequada.
- Nenhum bypass/force-push/deploy fora da política vigente.

## 7. Ambiente e promoção

- Ambiente alvo identificado.
- Branch/base/HEAD exatos registrados.
- `behind_by=0` e ausência de conflitos para mudanças pendentes.
- Evidência do ambiente alvo é atual.
- Promoção depende dos gates do ambiente e não de evidência de outro ambiente.

## 8. CI e qualidade

- Pre-PR/CI/gates obrigatórios verdes no HEAD atual.
- Testes funcionais e E2E aplicáveis verdes.
- Evidência antiga é invalidada quando o SHA muda.
- Falha determinística é corrigida na causa, não contornada.
- Checks report-only não substituem checks bloqueantes.

## Critérios por nível

### Acesso controlado

Exige evidência de identidade, navegação, jornada principal, segurança mínima e E2E do ambiente autorizado.

### Beta operacional

Além do acesso controlado, exige monitoramento, auditoria, indicadores rastreáveis e suporte operacional.

### Produção

Além dos níveis anteriores, exige evidência específica de produção, políticas/RBAC, observabilidade, recuperação e todos os gates de promoção vigentes.

## Evidência mínima de decisão

Registrar:

- ambiente;
- commit/versão;
- correlation_id quando aplicável;
- runs/checks relevantes;
- E2E;
- riscos residuais;
- decisão e responsável.

Se qualquer evidência obrigatória estiver ausente ou desatualizada, o estado correto é **não comprovado**, não “pronto”.
