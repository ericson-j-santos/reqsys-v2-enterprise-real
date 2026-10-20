#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
engine_root="${GITHUB_WORKSPACE}/.external/ocr-engine"
evidence_root="${GITHUB_WORKSPACE}/proxy-evidence"

require_env() {
  local name="$1"
  test -n "${!name:-}" || { echo "missing required env: $name" >&2; exit 2; }
}

for name in OCR_REPOSITORY OCR_SOURCE_SHA OCR_MAIN_SHA OCR_CI_BLOB_SHA CORRELATION_ID GITHUB_WORKSPACE GITHUB_REPOSITORY GITHUB_SHA RUNNER_TEMP GH_TOKEN; do
  require_env "$name"
done

verify_source() {
  test -d "$engine_root/.git"
  test "$(git -C "$engine_root" rev-parse HEAD)" = "$OCR_SOURCE_SHA"
  test "$(git -C "$engine_root" hash-object .github/workflows/ci.yml)" = "$OCR_CI_BLOB_SHA"
  test "$(gh api "repos/$OCR_REPOSITORY/git/ref/heads/main" --jq '.object.sha')" = "$OCR_MAIN_SHA"
  test "$(gh api "repos/$OCR_REPOSITORY/git/ref/heads/audit/baseline92-reference-v1.0-20261020" --jq '.object.sha')" = "$OCR_SOURCE_SHA"
}

install_dev() {
  cd "$engine_root"
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev]"
}

run_test_mode() {
  verify_source
  install_dev
  cd "$engine_root"
  python -m compileall -q src scripts
  python -m pytest -q
  set +e
  python scripts/ocr_dataset_policy.py midv-2020 --context corporate-ci --accepted
  code=$?
  set -e
  test "$code" -eq 3
  python -m build
  echo "OCR_PROXY_TEST_MODE_OK python=$(python --version 2>&1)"
}

run_evidence_mode() {
  verify_source
  cd "$engine_root"
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends     tesseract-ocr tesseract-ocr-por imagemagick poppler-utils fonts-dejavu-core
  python -m pip install --upgrade pip build
  python -m pip install -e ".[dev]"
  mkdir -p artifacts "$evidence_root"

  python scripts/validate_baseline92_contract_disposition.py     --repository-root .     --output "$RUNNER_TEMP/contract-disposition.json" >/dev/null
  python -m pytest -q tests/test_baseline92_contract_disposition.py

  python scripts/ocr_benchmark.py     --output artifacts/ocr-benchmark.json     synthetic     --workdir artifacts/ocr-work

  printf '%s\n' '{"expected":"MARIA SILVA","predicted":"MAR1A SILVA","state":"AUTO"}'     > artifacts/negative.jsonl
  set +e
  python scripts/ocr_benchmark.py     --output artifacts/negative-gate.json     --exact-min 0     --cer-max 1     --false-auto-max 0     evaluate artifacts/negative.jsonl
  code=$?
  set -e
  test "$code" -eq 2
  python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("artifacts/negative-gate.json").read_text(encoding="utf-8"))
assert payload["gate"] == "FAIL"
assert payload["metrics"]["false_auto_total"] == 1
PY

  mkdir -p artifacts/distribution
  export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
  export PYTHONHASHSEED=0
  python -m build --wheel --outdir artifacts/distribution
  python scripts/ocr_distribution_evidence.py generate     --bundle-dir artifacts/distribution     --repository "$OCR_REPOSITORY"     --git-sha "$OCR_SOURCE_SHA"
  python scripts/ocr_distribution_evidence.py verify     --bundle-dir artifacts/distribution     --expected-repository "$OCR_REPOSITORY"     --expected-git-sha "$OCR_SOURCE_SHA"

  rm -rf "$RUNNER_TEMP/tampered-distribution"
  cp -a artifacts/distribution "$RUNNER_TEMP/tampered-distribution"
  python - <<'PY'
import os
from pathlib import Path
root = Path(os.environ["RUNNER_TEMP"]) / "tampered-distribution"
wheel = next(root.glob("*.whl"))
with wheel.open("ab") as handle:
    handle.write(b"TAMPER")
PY
  set +e
  output="$(python scripts/ocr_distribution_evidence.py verify     --bundle-dir "$RUNNER_TEMP/tampered-distribution"     --expected-repository "$OCR_REPOSITORY"     --expected-git-sha "$OCR_SOURCE_SHA" 2>&1)"
  code=$?
  set -e
  printf '%s\n' "$output"
  test "$code" -eq 2
  printf '%s\n' "$output" | grep -Eq 'code=(size_mismatch|sha256_mismatch)'

  wheel="$(find artifacts/distribution -maxdepth 1 -type f -name 'ocr_evidence_engine-*.whl' -print -quit)"
  test -n "$wheel"
  python -m venv "$RUNNER_TEMP/ocr-consumer-venv"
  "$RUNNER_TEMP/ocr-consumer-venv/bin/python" -m pip install --no-deps "$wheel"
  (
    cd "$RUNNER_TEMP"
    "$RUNNER_TEMP/ocr-consumer-venv/bin/python" - <<'PY'
from ocr_evidencia import __version__
from ocr_evidencia.dominio.nome import EstadoConsensoNome, LeituraOCRNome, consensuar_nome
assert __version__ == "1.2.0"
result = consensuar_nome([
    LeituraOCRNome("MARIA SILVA", 1.0, origem="proxy-a"),
    LeituraOCRNome("MARIA SILVA", 1.0, origem="proxy-b"),
    LeituraOCRNome("MARIA SILVA", 1.0, origem="proxy-c"),
])
assert result.valor == "MARIA SILVA"
assert result.estado is EstadoConsensoNome.AUTO
print("EXTERNAL_CONSUMER_OK")
PY
  )

  python scripts/gold_standard_gate.py     --expected-sha "$OCR_SOURCE_SHA"     --output artifacts/gold-standard.json
  mkdir -p artifacts/repro/a artifacts/repro/b
  python -m build --wheel --outdir artifacts/repro/a
  python -m build --wheel --outdir artifacts/repro/b
  a="$(find artifacts/repro/a -maxdepth 1 -type f -name '*.whl' -print -quit)"
  b="$(find artifacts/repro/b -maxdepth 1 -type f -name '*.whl' -print -quit)"
  test -n "$a" && test -n "$b"
  cmp "$a" "$b"
  sha256sum "$a" "$b" > "$RUNNER_TEMP/reproducible-wheel.sha256"

  trap 'rm -f src/ocr_evidencia/_gold_negative_control.py' EXIT
  printf '%s\n' 'import socket' > src/ocr_evidencia/_gold_negative_control.py
  set +e
  output="$(python scripts/gold_standard_gate.py --expected-sha "$OCR_SOURCE_SHA" 2>&1)"
  code=$?
  set -e
  printf '%s\n' "$output"
  test "$code" -eq 2
  printf '%s\n' "$output" | grep -q 'network_import_forbidden:'
  rm -f src/ocr_evidencia/_gold_negative_control.py
  trap - EXIT

  python scripts/gold_standard_gate.py     --expected-sha "$OCR_SOURCE_SHA"     --output artifacts/gold-standard.json

  python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["GITHUB_WORKSPACE"]) / ".external" / "ocr-engine"
evidence_root = Path(os.environ["GITHUB_WORKSPACE"]) / "proxy-evidence"
contract = json.loads((Path(os.environ["RUNNER_TEMP"]) / "contract-disposition.json").read_text())
benchmark_path = root / "artifacts/ocr-benchmark.json"
negative_path = root / "artifacts/negative-gate.json"
gold_path = root / "artifacts/gold-standard.json"
benchmark = json.loads(benchmark_path.read_text())
negative = json.loads(negative_path.read_text())
distribution = sorted((root / "artifacts/distribution").iterdir())
wheels = [path for path in distribution if path.suffix == ".whl"]
assert len(wheels) == 1
repro_a = next((root / "artifacts/repro/a").glob("*.whl"))
repro_b = next((root / "artifacts/repro/b").glob("*.whl"))
assert repro_a.read_bytes() == repro_b.read_bytes()

assert contract["status"] == "VALIDATED_REFERENCE_ONLY_NO_MIGRATION"
assert contract["current_engine"]["baseline_functional_certified"] is False
assert contract["current_engine"]["semantic_equivalence"] == "NOT_PROVEN"
assert contract["historical_test_bodies_executed_by_this_validation"] == 0
assert contract["decisions"] == {"PRESERVE_REFERENCE_ONLY": 5, "SEPARATE": 3}\nassert "MIGRATE" not in contract["decisions"]
assert len(contract["negative_controls_passed"]) == 21
assert negative["gate"] == "FAIL"
assert negative["metrics"]["false_auto_total"] == 1

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

payload = {
    "schema_version": "1.0.0",
    "correlation_id": os.environ["CORRELATION_ID"],
    "public_executor_repository": os.environ["GITHUB_REPOSITORY"],
    "public_executor_sha": os.environ["GITHUB_SHA"],
    "public_runner": "ubuntu-latest",
    "cost_classification": "COST_ZERO_CONFIRMED_PUBLIC_STANDARD_RUNNER",
    "private_source": {
        "repository": os.environ["OCR_REPOSITORY"],
        "commit_sha": os.environ["OCR_SOURCE_SHA"],
        "main_sha_observed": os.environ["OCR_MAIN_SHA"],
        "ci_blob_sha": os.environ["OCR_CI_BLOB_SHA"],
        "raw_private_bytes_uploaded": False,
    },
    "matrix": {
        "python_versions_required": ["3.11", "3.12"],
        "evidence_job_depends_on_matrix_success": True,
    },
    "contract_disposition": {
        "status": contract["status"],
        "decisions": contract["decisions"],\n        "migrate_count": 0,
        "negative_controls_passed": len(contract["negative_controls_passed"]),
        "baseline_functional_certified": contract["current_engine"]["baseline_functional_certified"],
        "semantic_equivalence": contract["current_engine"]["semantic_equivalence"],
        "historical_test_bodies_executed": contract["historical_test_bodies_executed_by_this_validation"],
    },
    "benchmark": {
        "gate": benchmark.get("gate"),
        "metrics": benchmark.get("metrics", {}),
        "sha256": digest(benchmark_path),
        "negative_gate_control_passed": True,
        "negative_gate_sha256": digest(negative_path),
    },
    "distribution": {
        "verified": True,
        "tamper_negative_control_passed": True,
        "external_consumer_passed": True,
        "files": [
            {"name": path.name, "size": path.stat().st_size, "sha256": digest(path)}
            for path in distribution
        ],
        "private_distribution_uploaded": False,
    },
    "gold_standard": {
        "positive_gate_passed": True,
        "negative_network_import_control_passed": True,
        "final_revalidation_passed": True,
        "gold_evidence_sha256": digest(gold_path),
        "reproducible_wheel_byte_identical": True,
        "reproducible_wheel_sha256": digest(repro_a),
    },
    "production_touched": False,
    "private_repository_mutated": False,
    "pin_changed": False,
}
evidence_root.mkdir(parents=True, exist_ok=True)
out = evidence_root / "evidence.json"
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(evidence_root / "SHA256SUMS").write_text(
    digest(out) + "  evidence.json\n",
    encoding="utf-8",
)
print(json.dumps(payload, sort_keys=True))
PY

  test "$(find "$evidence_root" -type f | wc -l)" -eq 2
  test -f "$evidence_root/evidence.json"
  test -f "$evidence_root/SHA256SUMS"
  test "$(find "$evidence_root" -type f \( -name '*.py' -o -name '*.whl' -o -name '*.zip' \) | wc -l)" -eq 0
  test "$(du -sb "$evidence_root" | cut -f1)" -lt 100000
  (
    cd "$evidence_root"
    sha256sum -c SHA256SUMS
  )
  cd "$GITHUB_WORKSPACE"
  rm -rf .external
  test ! -e .external
  echo "OCR_PROXY_EVIDENCE_MODE_OK"
}

case "$mode" in
  test) run_test_mode ;;
  evidence) run_evidence_mode ;;
  *) echo "usage: $0 {test|evidence}" >&2; exit 2 ;;
esac
