# CHECKLIST OPERACIONAL - ATUALIZACAO CONTINUA

Objetivo: garantir criacao, atualizacao e manutencao continua de dados, informacoes, aplicacoes, softwares e codigos em cada entrega.

## 1. Diagnostico inicial

- Identificar o que ja existe e o que esta desatualizado.
- Identificar lacunas (o que precisa ser criado).
- Registrar escopo minimo da atualizacao.

## 2. Criacao e atualizacao tecnica

- Criar artefatos ausentes (arquivos, endpoints, scripts, configs, docs).
- Atualizar artefatos existentes sem quebrar compatibilidade desnecessaria.
- Manter padrao de versao, nomenclatura e organizacao do projeto.

## 3. Dados e informacoes

- Atualizar dados operacionais necessarios para o fluxo atual.
- Atualizar documentacao funcional e tecnica impactada.
- Confirmar que links, referencias e exemplos estao coerentes com a versao atual.

## 4. Validacao

- Executar validacoes tecnicas (build, teste, lint, health checks aplicaveis).
- Validar comportamento principal apos alteracoes.
- Corrigir regressao antes de finalizar.

## 5. Governanca da entrega

- Atualizar CHANGELOG com o que foi criado/alterado/corrigido.
- Registrar versao quando aplicavel (tag/release/pacote).
- Garantir rastreabilidade minima da mudanca (descricao clara de impacto).

## 6. Fechamento

- Confirmar estado final atualizado e consistente.
- Listar pendencias remanescentes, se houver.
- Definir proximo ciclo de atualizacao continua.

---

## Modo de uso rapido por tarefa

- Antes de iniciar: preencher mentalmente os itens 1 e 2.
- Durante execucao: cumprir itens 2 e 3.
- Antes de concluir: cumprir itens 4, 5 e 6.

## Regra permanente

Sempre priorizar: criar quando faltar, atualizar quando existir, e manter tudo continuamente atualizado durante as entregas.
