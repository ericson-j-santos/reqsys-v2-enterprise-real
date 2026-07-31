#!/usr/bin/env python3
"""Patch Governed Merge Queue with a fail-closed current-SHA stability job."""

from __future__ import annotations

import argparse
from pathlib import Path


STABILITY_JOB = r'''  current-sha-stability:
    name: Estabilidade dos workflows no SHA atual
    runs-on: ubuntu-latest
    timeout-minutes: 12
    needs: resolve-context
    steps:
      - name: Checkout do SHA avaliado
        uses: actions/checkout@v4
        with:
          ref: ${{ needs.resolve-context.outputs.head_sha }}

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Aguardar registro e conclusão dos workflows críticos
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ needs.resolve-context.outputs.pr_number }}
          EVALUATED_SHA: ${{ needs.resolve-context.outputs.head_sha }}
        shell: bash
        run: |
          set -euo pipefail
          mkdir -p artifacts/governed-merge-queue .tmp/current-sha-stability
          policy="governance/merge/current-sha-required-workflows.json"
          max_attempts="$(jq -r '.max_attempts' "$policy")"
          poll_seconds="$(jq -r '.poll_seconds' "$policy")"

          for attempt in $(seq 1 "$max_attempts"); do
            current_sha="$(gh pr view "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --json headRefOid --jq '.headRefOid')"
            gh api --method GET \
              "repos/${GITHUB_REPOSITORY}/actions/runs" \
              -f head_sha="$EVALUATED_SHA" \
              -f event="pull_request" \
              -f per_page=100 \
              > .tmp/current-sha-stability/workflow-runs.json

            set +e
            python scripts/evaluate_current_sha_workflow_stability.py \
              --runs .tmp/current-sha-stability/workflow-runs.json \
              --policy "$policy" \
              --evaluated-sha "$EVALUATED_SHA" \
              --current-sha "$current_sha" \
              --output artifacts/governed-merge-queue/current-sha-stability.json
            evaluation_code=$?
            set -e

            if [[ "$evaluation_code" == "0" ]]; then
              echo "Workflows críticos estabilizados para $EVALUATED_SHA na tentativa $attempt."
              break
            fi

            decision="$(jq -r '.decision' artifacts/governed-merge-queue/current-sha-stability.json)"
            echo "Tentativa $attempt/$max_attempts: $decision"
            if [[ "$decision" == "head_sha_changed" ]]; then
              echo "O head do PR mudou durante a avaliação; invalidando a decisão anterior."
              exit 1
            fi
            if [[ "$attempt" == "$max_attempts" ]]; then
              echo "Os workflows críticos não estabilizaram dentro da política governada."
              exit 1
            fi
            sleep "$poll_seconds"
          done

      - name: Publicar evidência de estabilidade do SHA
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: current-sha-workflow-stability
          path: artifacts/governed-merge-queue/current-sha-stability.json
          if-no-files-found: error
          retention-days: 30

'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_workflow(text: str) -> str:
    if "current-sha-stability:" in text or "REQSYS_CURRENT_SHA_STABILITY_GATE" in text:
        raise ValueError("current-SHA stability gate already present")

    text = replace_once(
        text,
        "  merge-queue-gate:\n",
        "  # REQSYS_CURRENT_SHA_STABILITY_GATE\n" + STABILITY_JOB + "  merge-queue-gate:\n",
        "job insertion",
    )
    text = replace_once(
        text,
        "    needs: [resolve-context, isolated-validation, temporary-integration]\n",
        "    needs: [resolve-context, isolated-validation, temporary-integration, current-sha-stability]\n",
        "merge gate needs",
    )
    text = replace_once(
        text,
        "      - name: Setup Python\n        uses: actions/setup-python@v5\n        with:\n          python-version: ${{ env.PYTHON_VERSION }}\n\n      - name: Consolidar política e elegibilidade\n",
        "      - name: Setup Python\n        uses: actions/setup-python@v5\n        with:\n          python-version: ${{ env.PYTHON_VERSION }}\n\n      - name: Baixar evidência de estabilidade do SHA atual\n        uses: actions/download-artifact@v4\n        with:\n          name: current-sha-workflow-stability\n          path: artifacts/governed-merge-queue\n\n      - name: Consolidar política e elegibilidade\n",
        "stability evidence download",
    )
    text = replace_once(
        text,
        '          ISOLATED="${{ needs.isolated-validation.result }}"\n          INTEGRATION="${{ needs.temporary-integration.result }}"\n',
        '          ISOLATED="${{ needs.isolated-validation.result }}"\n          INTEGRATION="${{ needs.temporary-integration.result }}"\n          STABILITY="${{ needs.current-sha-stability.result }}"\n',
        "stability result variable",
    )
    text = replace_once(
        text,
        '          if [ "$ISOLATED" != "success" ]; then\n            CI_STATUS="red"\n          fi\n',
        '          if [ "$ISOLATED" != "success" ] || [ "$STABILITY" != "success" ]; then\n            CI_STATUS="red"\n          fi\n',
        "eligibility condition",
    )
    text = replace_once(
        text,
        '            --arg integration_result "$INTEGRATION" \\\n            --arg merge_path "governed_pr_automation" \\\n            --slurpfile runtime_gate artifacts/governed-merge-queue/runtime-merge-queue-gate.json \\\n',
        '            --arg integration_result "$INTEGRATION" \\\n            --arg stability_result "$STABILITY" \\\n            --arg merge_path "governed_pr_automation" \\\n            --slurpfile runtime_gate artifacts/governed-merge-queue/runtime-merge-queue-gate.json \\\n            --slurpfile sha_stability artifacts/governed-merge-queue/current-sha-stability.json \\\n',
        "jq stability arguments",
    )
    text = replace_once(
        text,
        '                isolated_validation: $isolated_result,\n                temporary_integration: $integration_result\n              },\n',
        '                isolated_validation: $isolated_result,\n                temporary_integration: $integration_result,\n                current_sha_stability: $stability_result\n              },\n              current_sha_stability: $sha_stability[0],\n',
        "policy stability evidence",
    )
    text = replace_once(
        text,
        '          | Integração temporária | \\`$INTEGRATION\\` |\n          | Runtime merge queue gate | \\`$ELIGIBLE\\` |\n',
        '          | Integração temporária | \\`$INTEGRATION\\` |\n          | Estabilidade do SHA atual | \\`$STABILITY\\` |\n          | Runtime merge queue gate | \\`$ELIGIBLE\\` |\n',
        "summary stability row",
    )
    text = replace_once(
        text,
        '            artifacts/governed-merge-queue/runtime-merge-queue-gate.json\n',
        '            artifacts/governed-merge-queue/runtime-merge-queue-gate.json\n            artifacts/governed-merge-queue/current-sha-stability.json\n',
        "policy artifact evidence",
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    patched = patch_workflow(args.workflow.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(patched, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
