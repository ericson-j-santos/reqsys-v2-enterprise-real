# Analisador de Legado VBA — grafo interprocedural

## Objetivo

Evoluir a análise estática do ReqSys para reconstruir chamadas entre procedimentos e, em contêineres Office, entre módulos do mesmo projeto VBA, sem executar Excel, Word ou macros.

## Capacidades

O incremento adiciona:

- grafo de procedimentos por módulo;
- resolução de `Call Procedimento(...)`;
- resolução de `Application.Run "Procedimento", ...` quando o alvo é literal e único;
- resolução de chamadas de função em expressões;
- vínculo posicional argumento → parâmetro para fontes VBA textuais;
- identificação de `Application.Run` com alvo dinâmico;
- detecção de chamadas literais sem destino conhecido;
- resolução entre módulos para contêineres Office já extraídos;
- identificação de destinos ambíguos sem escolher automaticamente um candidato;
- detecção de ciclos e recursão direta/indireta;
- contadores rastreáveis no `summary`.

## Segurança e governança

Invariantes preservados:

- `analysis_type=static_only`;
- `execution_performed=false`;
- nenhum `Application.Run` é executado;
- argumentos literais são substituídos por `<literal>` no grafo;
- chamadas dinâmicas, ambíguas ou externas permanecem como pendência de revisão humana;
- a análise não incorpora requisitos automaticamente e não persiste o código-fonte.

## Saída

A resposta passa a expor `call_graph` com:

- `nodes`: procedimentos conhecidos;
- `edges`: chamadas resolvidas;
- `dynamic_or_unresolved_calls`: alvos que não podem ser resolvidos com evidência suficiente;
- `cycles`: ciclos de chamadas;
- `summary`: procedimentos, arestas resolvidas, pendências e ciclos.

Para fonte textual, as arestas também incluem `parameter_bindings` com posição, parâmetro, argumento sanitizado e referências de origem.

## Limitações

A resolução é conservadora. Em projetos Office, quando dois módulos expõem procedimentos com o mesmo nome, o ReqSys marca `AMBIGUOUS_TARGET` em vez de inferir um destino. Chamadas construídas em tempo de execução continuam sem resolução automática e exigem revisão humana ou análise dinâmica futura em ambiente isolado.
