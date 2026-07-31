#!/usr/bin/env python3
from pathlib import Path
import re

DELIVERY = Path(".github/workflows/padrao-ouro-delivery-automation.yml")
REUSABLE = Path(".github/workflows/bacen-production-hard-gate.yml")
MARKER = "# REQSYS_PRODUCTION_GOVERNANCE_GATE\n"


def replace_in_job(text: str, job_name: str, old: str, new: str) -> str:
    start_marker = f"\n  {job_name}:\n"
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"job {job_name} not found")
    following = re.search(r"\n  [A-Za-z0-9_-]+:\n", text[start + len(start_marker):])
    end = len(text) if following is None else start + len(start_marker) + following.start()
    section = text[start:end]
    if section.count(old) != 1:
        raise SystemExit(f"{job_name} dependency contract changed")
    section = section.replace(old, new, 1)
    return text[:start] + section + text[end:]


# Expose the reusable workflow decision without changing the gate implementation.
reusable = REUSABLE.read_text(encoding="utf-8")
old_call = """      enforce:
        description: Fail the caller while production is not formally allowed
        required: false
        type: boolean
        default: true
  workflow_dispatch:
"""
new_call = """      enforce:
        description: Fail the caller while production is not formally allowed
        required: false
        type: boolean
        default: true
    outputs:
      production_allowed:
        description: Whether the BACEN evidence authorizes production
        value: ${{ jobs.gate.outputs.production_allowed }}
      decision:
        description: BACEN production decision
        value: ${{ jobs.gate.outputs.decision }}
  workflow_dispatch:
"""
if reusable.count(old_call) != 1:
    raise SystemExit("reusable workflow_call contract changed")
reusable = reusable.replace(old_call, new_call, 1)
REUSABLE.write_text(reusable, encoding="utf-8")

text = DELIVERY.read_text(encoding="utf-8")
if text.startswith(MARKER):
    raise SystemExit("delivery workflow already protected")

configure_anchor = "\n  configure-prod-secrets:\n"
gate_block = """
  production-gate:
    name: BACEN authorization for production delivery
    if: >-
      (github.event_name == 'push' && github.ref_name == 'main') ||
      (github.event_name == 'pull_request' && github.event.pull_request.merged == true) ||
      (github.event_name == 'workflow_dispatch' &&
       (github.event.inputs.action == 'deploy_runtime_only' || github.event.inputs.action == 'auto'))
    uses: ./.github/workflows/bacen-production-hard-gate.yml
    with:
      enforce: ${{ github.event_name == 'workflow_dispatch' }}

"""
if text.count(configure_anchor) != 1:
    raise SystemExit("configure-prod-secrets anchor not found exactly once")
text = text.replace(configure_anchor, "\n" + gate_block + "  configure-prod-secrets:\n", 1)

old_configure = """    needs: validate-runtime
    if: >-
      needs.validate-runtime.result == 'success' &&
"""
new_configure = """    needs: [validate-runtime, production-gate]
    if: >-
      needs.validate-runtime.result == 'success' &&
      needs.production-gate.result == 'success' &&
      needs.production-gate.outputs.production_allowed == 'true' &&
"""
text = replace_in_job(text, "configure-prod-secrets", old_configure, new_configure)

old_backend = """    needs: [validate-runtime, configure-prod-secrets]
    if: >-
      needs.validate-runtime.result == 'success' &&
      needs.configure-prod-secrets.result == 'success' &&
"""
new_backend = """    needs: [validate-runtime, production-gate, configure-prod-secrets]
    if: >-
      needs.validate-runtime.result == 'success' &&
      needs.production-gate.result == 'success' &&
      needs.production-gate.outputs.production_allowed == 'true' &&
      needs.configure-prod-secrets.result == 'success' &&
"""
text = replace_in_job(text, "deploy-fly-prod", old_backend, new_backend)

old_frontend = """    needs: validate-runtime
    if: >-
      needs.validate-runtime.result == 'success' &&
"""
new_frontend = """    needs: [validate-runtime, production-gate]
    if: >-
      needs.validate-runtime.result == 'success' &&
      needs.production-gate.result == 'success' &&
      needs.production-gate.outputs.production_allowed == 'true' &&
"""
text = replace_in_job(text, "deploy-fly-frontend-prod", old_frontend, new_frontend)

old_summary_needs = """    needs: [auto-open-pr, validate-runtime, configure-prod-secrets, deploy-fly-prod, deploy-fly-frontend-prod, public-runtime-smoke]
"""
new_summary_needs = """    needs: [auto-open-pr, validate-runtime, production-gate, configure-prod-secrets, deploy-fly-prod, deploy-fly-frontend-prod, public-runtime-smoke]
"""
if text.count(old_summary_needs) != 1:
    raise SystemExit("delivery summary dependency contract changed")
text = text.replace(old_summary_needs, new_summary_needs, 1)

old_summary_row = """            echo "| Validate runtime | ${{ needs.validate-runtime.result || 'skipped' }} |"
            echo "| Configure secrets | ${{ needs.configure-prod-secrets.result || 'skipped' }} |"
"""
new_summary_row = """            echo "| Validate runtime | ${{ needs.validate-runtime.result || 'skipped' }} |"
            echo "| BACEN production gate | ${{ needs.production-gate.result || 'skipped' }} / allowed=${{ needs.production-gate.outputs.production_allowed || 'false' }} |"
            echo "| Configure secrets | ${{ needs.configure-prod-secrets.result || 'skipped' }} |"
"""
if text.count(old_summary_row) != 1:
    raise SystemExit("delivery summary row contract changed")
text = text.replace(old_summary_row, new_summary_row, 1)

text = MARKER + text
DELIVERY.write_text(text, encoding="utf-8")
print("Padrão Ouro productive jobs protected by reusable BACEN authorization")
