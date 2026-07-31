#!/usr/bin/env python3
from pathlib import Path

WORKFLOW = Path(".github/workflows/fly-environment-homologation-gate.yml")
MARKER = "# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"

text = WORKFLOW.read_text(encoding="utf-8")
if text.startswith(MARKER):
    raise SystemExit("workflow already protected")

job_anchor = "\n  deploy:\n"
gate_block = """
  production-gate:
    name: BACEN authorization for production homologation
    if: ${{ inputs.environment == 'prod' && inputs.deploy == true }}
    uses: ./.github/workflows/bacen-production-hard-gate.yml
    with:
      enforce: true

"""
if text.count(job_anchor) != 1:
    raise SystemExit("deploy job anchor not found exactly once")
text = text.replace(job_anchor, "\n" + gate_block + "  deploy:\n", 1)

old_dependency = """    needs: preflight
    if: always() && needs.preflight.result == 'success'
"""
new_dependency = """    needs:
      - preflight
      - production-gate
    if: >-
      always() &&
      needs.preflight.result == 'success' &&
      (needs.production-gate.result == 'success' || needs.production-gate.result == 'skipped')
"""
if text.count(old_dependency) != 1:
    raise SystemExit("deploy dependency contract changed")
text = text.replace(old_dependency, new_dependency, 1)

text = MARKER + text
WORKFLOW.write_text(text, encoding="utf-8")
print("Fly Environment Homologation Gate protected before production environment/secrets")
