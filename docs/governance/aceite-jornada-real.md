# Aceite pela jornada real do usuário

## Regra canônica

Nenhuma funcionalidade, incremento, ambiente ou aplicação pode ser declarada **100% aceita**, **concluída operacionalmente** ou equivalente apenas porque testes automatizados, cobertura, build, smoke ou health checks ficaram verdes.

O aceite final exige, cumulativamente:

1. testes automatizados relevantes aprovados;
2. deploy real aprovado e SHA publicado comprovado;
3. navegação em browser real contra o ambiente publicado, sem mocks/interceptações das integrações da jornada;
4. integrações externas reais aprovadas;
5. efeito de negócio real comprovado no destino esperado.

A fórmula operacional é:

```text
testes automatizados passaram
        +
deploy real passou
        +
browser real sem mocks passou
        +
integrações externas reais passaram
        +
efeito de negócio foi comprovado
        ↓
      100% aceito
```

Se qualquer camada estiver ausente, simulada, desatualizada ou sem referência de evidência, o estado obrigatório é `quality_blocked` e `one_hundred_percent_allowed=false`.

## O que não conta como aceite final

- Playwright com `page.route()` substituindo APIs da jornada;
- mocks de Planner, SharePoint, Power Automate, Graph ou outros sistemas externos;
- `/health` 200 isoladamente;
- build ou deploy verde sem uso real da funcionalidade;
- teste de contrato sem efeito no sistema de destino;
- screenshot ou afirmação manual sem evidência rastreável;
- teste local usado para declarar ambiente remoto aprovado.

Mocks continuam permitidos em testes unitários e de interface, mas devem ser classificados apenas como **testes automatizados**, nunca como evidência das camadas de browser real, integração real ou efeito de negócio.

## Gate executável

Política: `config/user-journey-acceptance-policy.json`.

Validador:

```bash
python scripts/user_journey_acceptance_gate.py \
  --evidence audit/user-journey/<feature>/acceptance-input.json \
  --output audit/user-journey/<feature>/acceptance-result.json \
  --strict
```

O processo encerra com código diferente de zero enquanto as cinco camadas não estiverem aprovadas.

## WSJF Planner → Excel

O workflow `.github/workflows/user-journey-acceptance-dev.yml` executa automaticamente após `Fly DEV Fast Deploy` e valida o perfil `wsjf_planner_excel_simples`.

Ele verifica:

- testes automatizados relevantes;
- SHA realmente publicado no DEV e runtime público;
- browser real em `reqsys-app-dev.fly.dev`, sem `page.route()` ou mocks;
- descoberta real Microsoft e validação de ambiente, grupo, Planner, `WSJF.xlsx`, conexões Planner/Excel e `tbDemandas`;
- identidade Microsoft real no runtime, incluindo Power Platform e Microsoft Graph;
- efeito de negócio Planner → Power Automate → Excel por evidência específica.

O efeito de negócio usa `scripts/wsjf_business_effect_gate.py`. Para aprovação, a evidência precisa comprovar, no mínimo:

- ambiente `dev`;
- `real=true` e ausência de mock;
- mesmo `TaskId` no Planner e no Excel;
- exatamente uma linha correspondente no Excel;
- campos locais preservados após nova sincronização;
- ausência de escrita de volta no Planner;
- execução fonte rastreável;
- evidência com no máximo 24 horas.

Enquanto o probe real de efeito de negócio não produzir essa evidência, o workflow deve permanecer vermelho. Isso é comportamento esperado: evita falso `100%`.

## Regra para agentes e relatórios

Ao informar status, separar sempre:

- **qualidade técnica**: testes/build/CI;
- **publicação**: deploy e SHA real;
- **aceite da jornada**: browser real + integrações reais + efeito de negócio.

A expressão `100%`, `concluído`, `operacionalmente aceito` ou equivalente só pode ser usada para a funcionalidade quando o artifact do gate de jornada indicar `accepted=true` e `one_hundred_percent_allowed=true`.
