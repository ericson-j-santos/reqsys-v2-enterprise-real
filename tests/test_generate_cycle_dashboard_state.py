from __future__ import annotations

from scripts import generate_cycle_dashboard_state as dashboard


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping

    def request(self, path: str):
        value = self.mapping[path]
        if isinstance(value, Exception):
            raise value
        return value


def repo_mapping(repository: str = "ericson-j-santos/reqsys-v2-enterprise-real"):
    return {
        f"/repos/{repository}": {
            "default_branch": "main",
            "html_url": f"https://github.com/{repository}",
            "visibility": "public",
            "updated_at": "2026-09-28T17:00:00Z",
            "pushed_at": "2026-09-28T17:00:00Z",
        },
        f"/repos/{repository}/commits/main": {
            "sha": "a" * 40,
            "html_url": f"https://github.com/{repository}/commit/{'a' * 40}",
            "commit": {"committer": {"date": "2026-09-28T17:00:00Z"}},
        },
        f"/repos/{repository}/pulls?state=open&per_page=100": [
            {
                "number": 2132,
                "title": "feat: painel vivo",
                "draft": True,
                "updated_at": "2026-09-28T17:01:00Z",
                "head": {"sha": "b" * 40},
                "html_url": f"https://github.com/{repository}/pull/2132",
            }
        ],
        f"/repos/{repository}/actions/runs?branch=main&per_page=20": {
            "workflow_runs": [
                {
                    "id": 9001,
                    "name": "CI Enterprise Fast",
                    "status": "completed",
                    "conclusion": "success",
                    "event": "push",
                    "head_sha": "a" * 40,
                    "created_at": "2026-09-28T17:00:00Z",
                    "updated_at": "2026-09-28T17:02:00Z",
                    "html_url": f"https://github.com/{repository}/actions/runs/9001",
                }
            ]
        },
    }


def workflow_mapping(repository: str):
    result = {}
    for workflow in {
        "todo-global-hourly-cycle.yml",
        *dashboard.RUNTIME_WORKFLOWS,
    }:
        result[
            f"/repos/{repository}/actions/workflows/{workflow}/runs?branch=main&per_page=5"
        ] = {
            "workflow_runs": [
                {
                    "id": 9100,
                    "name": workflow,
                    "status": "completed",
                    "conclusion": "success",
                    "event": "schedule",
                    "head_sha": "a" * 40,
                    "created_at": "2026-09-28T17:00:00Z",
                    "updated_at": "2026-09-28T17:03:00Z",
                    "html_url": f"https://github.com/{repository}/actions/runs/9100",
                }
            ]
        }
    return result


def test_repository_snapshot_reports_current_sha_prs_and_ci():
    repository = "ericson-j-santos/reqsys-v2-enterprise-real"
    client = FakeClient(repo_mapping(repository))

    result = dashboard.repository_snapshot(
        client,
        {
            "repository": repository,
            "label": "ReqSys Produto",
            "group": "produto",
            "priority": "P0",
        },
    )

    assert result["source_status"] == "available"
    assert result["main_sha"] == "a" * 40
    assert result["open_pr_count"] == 1
    assert result["open_prs"][0]["number"] == 2132
    assert result["latest_ci"]["conclusion"] == "success"


def test_repository_snapshot_fails_closed_for_inaccessible_repository():
    repository = "ericson-j-santos/private-project"
    client = FakeClient(
        {f"/repos/{repository}": dashboard.GitHubAPIError(404, "Not Found")}
    )

    result = dashboard.repository_snapshot(
        client,
        {"repository": repository, "label": "Privado", "group": "produto"},
    )

    assert result["source_status"] == "unavailable"
    assert result["error"] == "http_404"
    assert "main_sha" not in result
    assert "open_pr_count" not in result


def test_build_state_keeps_todo_global_as_projection_not_source_of_truth():
    repository = "ericson-j-santos/reqsys-v2-enterprise-real"
    mapping = repo_mapping(repository)
    mapping.update(workflow_mapping(repository))
    client = FakeClient(mapping)

    state = dashboard.build_state(
        client,
        projects=[
            {
                "repository": repository,
                "label": "ReqSys Produto",
                "group": "produto",
                "priority": "P0",
            }
        ],
        teams_certification={
            "state": "quality_blocked",
            "delivery_rate": 100.0,
            "monitor_rate": 39.29,
        },
        repository=repository,
        source_sha="c" * 40,
        run_id="999",
        generated_at="2026-09-28T17:05:00+00:00",
    )

    assert state["mode"] == "live"
    assert state["source"]["sha"] == "c" * 40
    assert state["coverage"]["percent"] == 100.0
    assert state["teams"]["certification"]["state"] == "quality_blocked"
    assert state["todo_global"]["source_role"] == "projection_health"
    assert state["todo_global"]["canonical_source"] == "TODO Global"
    assert state["reqsys"]["open_pr_count"] == 1
    assert len(state["runtime_pc24x7"]["workflows"]) == len(
        dashboard.RUNTIME_WORKFLOWS
    )


def test_private_repository_redacts_titles_links_and_sha():
    repository = "ericson-j-santos/private-project"
    mapping = repo_mapping(repository)
    mapping[f"/repos/{repository}"]["visibility"] = "private"
    client = FakeClient(mapping)

    result = dashboard.repository_snapshot(
        client,
        {
            "repository": repository,
            "label": "Projeto privado",
            "group": "produto",
            "priority": "P1",
        },
    )

    assert result["source_status"] == "available"
    assert result["visibility"] == "private"
    assert result["private_redacted"] is True
    assert result["repository"] is None
    assert result["open_pr_count"] == 1
    assert "open_prs" not in result
    assert "main_sha" not in result
    assert "html_url" not in result
    assert result["latest_ci"] == {
        "status": "completed",
        "conclusion": "success",
        "updated_at": "2026-09-28T17:02:00Z",
    }
