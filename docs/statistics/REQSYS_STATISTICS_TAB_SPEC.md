# ReqSys — Aba Estatísticas

Status: Proposto / incremento planejado
Data: 2026-06-21
Escopo: Aba operacional para estatísticas internas da solução e estatísticas externas auditáveis.

## 1. Objetivo

Implementar uma aba dedicada a estatísticas no ReqSys para apoiar uso próprio, acompanhamento operacional, maturidade da solução, análise de evolução e cruzamento controlado com informações externas.

A aba não deve declarar estados avançados sem evidência real. Todo indicador deve diferenciar estado atual evidenciado, meta alvo e tendência calculada.

## 2. Princípios

- Dados internos devem vir da própria solução, CI/CD, requisitos, uso, logs, auditoria, testes e governança.
- Dados externos devem ter fonte, URL/origem, data de coleta, método de atualização, validade, confiabilidade e versão do conector.
- Toda métrica deve possuir definição, fórmula, granularidade, dono, origem, atualização e política de retenção.
- Indicadores devem permitir drill-down para dados analíticos.
- Nenhum dado externo deve ser tratado como verdade absoluta sem rastreabilidade.
- Produção deve ser bloqueada caso indicadores críticos estejam sem origem, sem cálculo ou com mock indevido.

## 3. Blocos da aba

| Bloco | Finalidade | Exemplos |
|---|---|---|
| Visão Geral | Painel executivo da solução | maturidade, saúde, tendência, pendências |
| Requisitos | Qualidade e evolução dos requisitos | total, ambíguos, atômicos, com BDD, rastreáveis |
| Uso da Solução | Estatísticas de utilização | acessos, abas mais usadas, ações por usuário/perfil |
| Engenharia | CI/CD, PRs, branches, releases | tempo médio de CI, falhas recorrentes, lead time |
| Segurança e Governança | guard rails e conformidade | gates bloqueantes, violações, auditoria, LGPD |
| IA e RAG | qualidade da assistência por IA | consultas com fonte, confiança, lacunas, alucinação bloqueada |
| Estatísticas Externas | Dados de apoio externos | mercado, tecnologia, legislação, benchmarks, tendências |
| Analítico | Drill-down de qualquer indicador | tabela filtrável, trilha de evidência, exportação |

## 4. Indicadores iniciais recomendados

| Indicador | Origem | Fórmula / regra | Drill-down obrigatório |
|---|---|---|---|
| Maturidade evidenciada | Interna | média ponderada de critérios validados | critérios, evidências e pendências |
| Requisitos com BDD | Interna | requisitos com critérios BDD / total | lista de requisitos sem BDD |
| Requisitos ambíguos | Interna | requisitos com lacuna ou baixa confiança / total | lacunas por requisito |
| Cobertura de rastreabilidade | Interna | itens com origem + decisão + teste / total | matriz requisito-decisão-teste |
| Saúde do CI | GitHub Actions | workflows verdes / workflows totais | runs, jobs, erros e duração |
| Tempo médio de CI | GitHub Actions | média móvel das durações recentes | workflow, branch, PR e etapa |
| Falhas recorrentes | GitHub Actions | agrupamento por assinatura do erro | job, arquivo, comando, frequência |
| Guard rails violados | Runtime/CI | violações por categoria | evidência, severidade, bloqueio |
| Consultas IA com fonte | RAG/IA | respostas com fontes / respostas totais | consulta, fontes, confiança |
| Dados externos válidos | Conectores externos | fontes atualizadas e dentro da validade / total | fonte, data, TTL e status |

## 5. Modelo de dados mínimo

```ts
export type TipoOrigemEstatistica = 'interna' | 'externa';

export interface FonteEstatistica {
  id: string;
  tipo: TipoOrigemEstatistica;
  nome: string;
  origem: string;
  url?: string;
  coletadoEm: string;
  atualizadoEm?: string;
  ttlMinutos?: number;
  confiabilidade: 'alta' | 'media' | 'baixa';
  versaoConector?: string;
}

export interface IndicadorEstatistico {
  id: string;
  nome: string;
  descricao: string;
  categoria: string;
  valorAtual: number | string;
  unidade?: string;
  tendencia: 'subindo' | 'estavel' | 'caindo' | 'indefinida';
  estadoAtual: 'nao_medido' | 'critico' | 'atencao' | 'adequado' | 'avancado';
  estadoAlvo: 'adequado' | 'avancado' | 'excelencia';
  fonte: FonteEstatistica;
  evidencias: string[];
  pendencias: string[];
}
```

## 6. Guard rails

A aba Estatísticas deve bloquear publicação ou exibir estado `nao_medido` quando:

- indicador não possui fonte;
- indicador não possui fórmula documentada;
- dado externo não possui data de coleta;
- dado externo está fora do TTL;
- indicador está em mock mas marcado como real;
- tendência foi definida manualmente sem cálculo/evidência;
- estado atual foi promovido sem evidência validada;
- informação sensível aparece em logs, tabelas ou exportações.

## 7. Critérios de aceite

- Existe rota/aba `/estatisticas` ou equivalente no menu principal.
- A tela exibe visão executiva e blocos por categoria.
- Cada card permite abrir analítico filtrado.
- Cada indicador exibe origem, fórmula, data de atualização e confiabilidade.
- Dados externos são identificados visualmente como externos e auditáveis.
- Não há mistura entre estado atual evidenciado e estado alvo desejado.
- A documentação, ADR, testes e changelog estão versionados.
- CI valida ausência de mocks indevidos em produção.

## 8. Próximo incremento recomendado

Implementar primeiro a versão local/internal-first com dados internos mockados apenas em ambiente de desenvolvimento, já com contrato definitivo e tela navegável. Em seguida, conectar GitHub Actions, PRs, requisitos e fontes externas.
