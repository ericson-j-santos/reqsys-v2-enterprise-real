# ReqSys Engineering Orchestrator

Version 1.0.0 is a thin engineering-routing layer over the existing ReqSys Operational Orchestrator.

## Scope

It standardizes how ChatGPT, Codex, GitHub-connected agents, and workers choose roles, risks, human gates, evidence requirements, and handoffs.

It intentionally does not implement another queue, evidence ledger, runtime executor, or merge/deploy mechanism.

## Files

- `SKILL.md`: skill contract.
- `router.yaml`: deterministic routing contract.
- `guardrails.yaml`: risk/evidence/security contract.
- `system-prompt.md`: platform-neutral system behavior.
- `operational-prompt.md`: per-task execution protocol.
- `tests/*.yaml`: positive, risk-gate, and refusal/control cases.
- `scripts/validate_reqsys_engineering_orchestrator.py`: contract validator.
- `tests/test_reqsys_engineering_orchestrator_contract.py`: executable contract tests.

## Validation

Run:

```bash
python scripts/validate_reqsys_engineering_orchestrator.py
python -m pytest tests/test_reqsys_engineering_orchestrator_contract.py -q
```

The validator is dependency-free and treats the JSON subset used by the YAML contract files as YAML 1.2-compatible structured configuration.
