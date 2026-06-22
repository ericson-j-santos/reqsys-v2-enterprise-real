# Guardrails — CodeRabbit e Revisão IA Rápida

## Objetivo

Reduzir o tempo de revisão automatizada sem reduzir governança, qualidade, rastreabilidade ou segurança do ReqSys.

## Princípio operacional

Revisão IA é uma camada complementar. Ela não substitui CI determinístico, testes, validações de segurança, revisão humana quando necessária nem gates de produção.

## Estratégia canônica

```text
Micro PR → CI Fast → revisão IA objetiva → merge controlado → deep review condicional/pós-merge
```

## Regras de ouro

### 1. PR pequeno por padrão

Preferir:

- até 10 arquivos alterados;
- até 400 linhas alteradas;
- um domínio por PR;
- título com escopo claro.

Exemplos:

- `fix(actions): harden fly governed command center`
- `docs(governance): add CodeRabbit fast review guardrails`
- `feat(runtime): add health validator endpoint`

Evitar:

- PR agregador sem necessidade;
- mistura de frontend, backend, workflows, documentação e runtime no mesmo PR;
- alteração massiva de HTML/artefatos junto com código crítico.

### 2. Fast path obrigatório

O PR deve receber feedback rápido de:

- validação de YAML;
- lint/test mínimo afetado;
- guardrails de segurança/governança;
- validação de workflows quando `.github/workflows/**` mudar;
- documentação quando houver ADR ou decisão operacional.

### 3. Deep review por condição

Executar revisão profunda quando houver:

- label `deep-review`;
- label `full-ci`;
- alteração em autenticação/autorização;
- alteração em deploy/produção;
- alteração em política de segurança;
- alteração arquitetural ampla;
- execução em `main` ou nightly.

### 4. Arquivos de baixo valor para revisão IA

Evitar inflar revisão IA com:

- `dist/**`;
- `coverage/**`;
- `artifacts/**`;
- `docs/**/*.html` autocontidos;
- screenshots, imagens e snapshots;
- lockfiles quando não forem o alvo da mudança;
- outputs gerados.

### 5. CodeRabbit não deve ser gargalo absoluto

Para PRs pequenos e determinísticos, o gate principal deve ser o CI Fast. CodeRabbit pode permanecer como sinal adicional, especialmente quando estiver pendente, desde que a proteção de branch e as regras do repositório permitam.

Em produção, segurança e arquitetura transversal, CodeRabbit/deep review deve permanecer obrigatório ou explicitamente justificado.

## Labels recomendadas

| Label | Uso |
|---|---|
| `fast-path` | PR pequeno e objetivo, candidato a ciclo rápido. |
| `deep-review` | Exige revisão IA profunda. |
| `full-ci` | Exige esteira completa. |
| `docs-only` | Mudança apenas documental. |
| `workflow-only` | Mudança apenas em GitHub Actions. |
| `security-critical` | Segurança, auth, secrets, produção ou dados sensíveis. |

## Política recomendada por tipo de PR

| Tipo de PR | CI Fast | CodeRabbit | Deep Review |
|---|---:|---:|---:|
| Docs simples | Sim | Opcional | Não |
| Workflow pequeno | Sim | Opcional/assíncrono | Condicional |
| Backend pequeno | Sim | Sim | Condicional |
| Segurança/Auth | Sim | Sim | Sim |
| Arquitetura transversal | Sim | Sim | Sim |
| Release/main | Sim | Sim | Sim |

## Anti-padrões bloqueáveis

- Mega PR sem justificativa.
- PR que altera runtime e documentação massiva sem separação.
- Exigir deep review para toda mudança trivial.
- Usar CodeRabbit como substituto de teste.
- Declarar maturidade alta sem evidência real.

## Métricas de acompanhamento

Acompanhar:

- tempo médio até primeiro feedback do CI Fast;
- tempo médio até CodeRabbit concluir;
- número de arquivos por PR;
- linhas alteradas por PR;
- percentual de PRs `fast-path`;
- falhas pós-merge relacionadas a revisão reduzida.

## Decisão operacional final

O padrão preferencial do ReqSys passa a ser:

```text
PR pequeno + CI Fast como gate principal + CodeRabbit/deep review condicionado por risco
```

A estratégia preserva padrão ouro porque reduz espera sem remover controles; apenas desloca análises profundas para quando agregam valor real.
