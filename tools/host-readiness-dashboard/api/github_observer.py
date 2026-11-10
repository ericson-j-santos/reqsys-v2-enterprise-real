"""Observação auxiliar de pickups GitHub; NUNCA certifica readiness ou continuidade."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

# Repositórios e identidades físicas são valores fechados, não vindos de input HTTP.
HOST_TARGETS = {
    "desktop": ("ericson-j-santos/desktop-pc24x7-runtime", "DESKTOP-PDQK954-runtime"),
    "lenovo": ("ericson-j-santos/desktop-pc24x7-runtime", "DESKTOP-RP23OGS-runtime"),
    "noteri": ("ericson-j-santos/noteri-runtime", "Noteri-runtime"),
}
QUALIFICATION_STEP = "Verify governed host qualification"
RESPONSE_LIMIT = 1_048_576


class ObservationUnavailable(RuntimeError):
    """A fonte não pode ser comprovada; nenhum host se torna apto."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, target):
        return None


def github_json(path: str) -> dict:
    """GET restrito ao GitHub; sem URL/host arbitrário ou redirecionamentos."""
    if not re.fullmatch(r"repos/ericson-j-santos/(?:desktop-pc24x7-runtime|noteri-runtime)/actions/(?:runs\?per_page=8|runs/[1-9][0-9]*/jobs\?per_page=100)", path):
        raise ObservationUnavailable("github_path_not_allowed")
    url = "https://api.github.com/" + path
    token = os.environ.get("REQSYS_GITHUB_READ_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ReqSys-readiness-observer", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=7) as response:
            if response.status != 200:
                raise ObservationUnavailable("github_http_invalid")
            data = response.read(RESPONSE_LIMIT + 1)
        if len(data) > RESPONSE_LIMIT:
            raise ObservationUnavailable("github_response_too_large")
        parsed = json.loads(data)
    except (HTTPError, URLError, OSError, ValueError):
        raise ObservationUnavailable("github_read_unavailable") from None
    if not isinstance(parsed, dict):
        raise ObservationUnavailable("github_response_invalid")
    return parsed


def valid_timestamp(value, now):
    if not isinstance(value, str):
        return False
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return False
        age = (now - observed.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= 300
    except (OverflowError, ValueError):
        return False


def observations(reader=github_json, now=None):
    """Somente inventário de pickup; até um job com sucesso NÃO atesta host."""
    now = now or datetime.now(timezone.utc)
    cache = {}
    hosts = []
    for host_id, (repo, expected_runner) in HOST_TARGETS.items():
        result = {"id": host_id, "pickup_observed": False, "fresh": False,
                  "ready_for_work": False, "continuity_certified": False,
                  "evidence_type": "github_job_only", "run_id": None,
                  "job_id": None, "observed_at": None, "source_sha": None,
                  "evidence_url": None, "block": "gateway_receipt_and_lease_missing"}
        try:
            if repo not in cache:
                cache[repo] = reader(f"repos/{repo}/actions/runs?per_page=8")
            runs = cache[repo].get("workflow_runs")
            if not isinstance(runs, list) or len(runs) > 8:
                raise ObservationUnavailable("github_runs_invalid")
            for run in runs[:8]:
                if not isinstance(run, dict) or type(run.get("id")) is not int or run["id"] <= 0:
                    continue
                if run.get("repository", {}).get("full_name") != repo or not re.fullmatch(r"[0-9a-f]{40}", str(run.get("head_sha", ""))):
                    continue
                if run.get("status") != "completed" or run.get("conclusion") != "success":
                    continue
                jobs = reader(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100").get("jobs")
                if not isinstance(jobs, list) or len(jobs) > 100:
                    raise ObservationUnavailable("github_jobs_invalid")
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    if (job.get("runner_name") != expected_runner or type(job.get("runner_id")) is not int
                            or job["runner_id"] <= 0 or type(job.get("id")) is not int or job["id"] <= 0
                            or job.get("run_id") != run["id"] or job.get("status") != "completed"
                            or job.get("conclusion") != "success" or not isinstance(job.get("labels"), list)
                            or "self-hosted" not in job["labels"]):
                        continue
                    steps = job.get("steps")
                    if not isinstance(steps, list) or not any(isinstance(s, dict)
                            and s.get("name") == QUALIFICATION_STEP and s.get("status") == "completed"
                            and s.get("conclusion") == "success" for s in steps):
                        continue
                    link = f"https://github.com/{repo}/actions/runs/{run['id']}/job/{job['id']}"
                    if job.get("html_url") != link:
                        continue
                    result.update(pickup_observed=True, fresh=valid_timestamp(job.get("completed_at"), now),
                                  run_id=run["id"], job_id=job["id"], observed_at=job.get("completed_at"),
                                  source_sha=run["head_sha"], evidence_url=link)
                    break
                if result["pickup_observed"]:
                    break
        except (ObservationUnavailable, TypeError, AttributeError):
            result["block"] = "github_observation_unavailable"
        hosts.append(result)
    return {"schema_version": "1", "source": "github_official_api_observation_only",
            "ready_for_work": False, "continuity_certified": False, "hosts": hosts}
