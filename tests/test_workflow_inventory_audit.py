from scripts import workflow_inventory_audit as audit


def test_parse_core_fields():
    text = '''name: Example CI

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  actions: write

jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: evidence-json
          path: out.json
      - run: echo "${{ secrets.API_TOKEN }}" >/dev/null
'''
    assert audit.parse_name(text, "x") == "Example CI"
    assert audit.parse_triggers(text) == ["push", "workflow_dispatch"]
    assert audit.parse_permissions(text) == ["actions:write", "contents:read"]
    assert audit.parse_secrets(text) == ["API_TOKEN"]
    assert audit.parse_artifacts(text) == ["evidence-json"]


def test_dependency_resolution_and_safe_classification():
    workflows = {
        ".github/workflows/base.yml": '''name: Base\non:\n  workflow_call:\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n''',
        ".github/workflows/caller.yml": '''name: Caller\non:\n  workflow_dispatch:\njobs:\n  c:\n    uses: ./.github/workflows/base.yml\n''',
    }
    records = audit.build_inventory(workflows, {}, {"counts": {}})
    by_path = {record.path: record for record in records}
    assert by_path[".github/workflows/base.yml"].callers == [".github/workflows/caller.yml"]
    assert by_path[".github/workflows/base.yml"].recommendation == "MANTER"


def test_workflow_run_dependency_by_name():
    workflows = {
        ".github/workflows/source.yml": '''name: Source\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n''',
        ".github/workflows/watch.yml": '''name: Watch Evidence\non:\n  workflow_run:\n    workflows:\n      - Source\n    types: [completed]\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "$GITHUB_STEP_SUMMARY"\n''',
    }
    records = audit.build_inventory(workflows, {}, {"counts": {}})
    by_path = {record.path: record for record in records}
    assert by_path[".github/workflows/source.yml"].callers == [".github/workflows/watch.yml"]
    assert by_path[".github/workflows/watch.yml"].recommendation == "FUNDIR"
    assert by_path[".github/workflows/watch.yml"].requires_human_validation is True


def test_dispatcher_is_never_auto_removed():
    workflows = {
        ".github/workflows/actions-dispatcher.yml": '''name: Actions Dispatcher — ReqSys\non:\n  workflow_dispatch:\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n'''
    }
    records = audit.build_inventory(workflows, {}, {"counts": {}})
    assert records[0].recommendation == "TRANSFORMAR_EM_REUTILIZAVEL"
    assert records[0].confidence == "alta"
