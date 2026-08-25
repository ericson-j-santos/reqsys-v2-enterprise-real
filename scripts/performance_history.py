#!/usr/bin/env python3
"""Histórico rolling 7/30 dias e regressão percentual do Dynamic Performance Gate."""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

VERSION = "1.1.0"
DEFAULT_ARTIFACT_NAME = "dynamic-performance-evidence-main"
API_HIGHER_WORSE = ("p95_ms", "p99_ms")
BROWSER_HIGHER_WORSE = (
    "event_loop_lag_p95_ms",
    "event_loop_lag_max_ms",
    "max_long_task_ms",
    "lcp_ms",
    "heap_after_gc_mb",
    "gc_roundtrip_ms",
)


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def snapshot_from_reports(
    api: dict[str, Any],
    browser: dict[str, Any],
    *,
    run_id: str,
    event_name: str,
    head_sha: str,
    head_branch: str,
    mode: str,
) -> dict[str, Any]:
    endpoints: dict[str, dict[str, float]] = {}
    for item in api.get("results", []):
        path = str(item.get("path") or "")
        metrics = item.get("metrics") or {}
        if path:
            endpoints[path] = {
                key: float(metrics.get(key, 0.0))
                for key in (
                    "p50_ms",
                    "p95_ms",
                    "p99_ms",
                    "avg_ms",
                    "max_ms",
                    "throughput_rps",
                    "error_rate_percent",
                )
            }

    browser_metrics = browser.get("metrics") or {}
    selected_browser: dict[str, float | None] = {}
    for key in (
        "event_loop_lag_p95_ms",
        "event_loop_lag_max_ms",
        "long_task_count",
        "max_long_task_ms",
        "lcp_ms",
        "heap_before_gc_mb",
        "heap_after_gc_mb",
        "heap_reclaimed_mb",
        "gc_roundtrip_ms",
    ):
        value = browser_metrics.get(key)
        selected_browser[key] = None if value is None else float(value)

    generated_at = browser.get("generated_at")
    if generated_at:
        observed_at = parse_iso(str(generated_at))
    elif api.get("generated_at_epoch") is not None:
        observed_at = datetime.fromtimestamp(float(api["generated_at_epoch"]), tz=UTC)
    else:
        observed_at = datetime.now(UTC)

    return {
        "schema_version": "1.0.0",
        "observed_at": iso_utc(observed_at),
        "run_id": str(run_id),
        "event_name": event_name,
        "head_sha": head_sha,
        "head_branch": head_branch,
        "mode": mode,
        "api": endpoints,
        "browser": selected_browser,
    }


def snapshot_key(snapshot: dict[str, Any]) -> tuple[str, str]:
    return str(snapshot.get("run_id") or ""), str(snapshot.get("observed_at") or "")


def merge_and_prune(
    history: list[dict[str, Any]],
    current: dict[str, Any],
    *,
    retention_days: int,
) -> list[dict[str, Any]]:
    cutoff = parse_iso(current["observed_at"]) - timedelta(days=retention_days)
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in [*history, current]:
        try:
            observed = parse_iso(str(item["observed_at"]))
        except (KeyError, TypeError, ValueError):
            continue
        if observed >= cutoff:
            merged[snapshot_key(item)] = item
    return sorted(merged.values(), key=lambda item: parse_iso(item["observed_at"]))


def _median(values: list[float]) -> float | None:
    return None if not values else round(float(statistics.median(values)), 4)


def _window_samples(
    history: list[dict[str, Any]],
    current: dict[str, Any],
    window_days: int,
) -> list[dict[str, Any]]:
    current_at = parse_iso(current["observed_at"])
    cutoff = current_at - timedelta(days=window_days)
    current_key = snapshot_key(current)
    return [
        item
        for item in history
        if snapshot_key(item) != current_key
        and cutoff <= parse_iso(item["observed_at"]) < current_at
    ]


def build_baselines(
    history: list[dict[str, Any]],
    current: dict[str, Any],
    *,
    windows_days: list[int],
    minimum_samples: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    api_keys = (
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "avg_ms",
        "max_ms",
        "throughput_rps",
        "error_rate_percent",
    )
    browser_keys = (
        "event_loop_lag_p95_ms",
        "event_loop_lag_max_ms",
        "long_task_count",
        "max_long_task_ms",
        "lcp_ms",
        "heap_before_gc_mb",
        "heap_after_gc_mb",
        "heap_reclaimed_mb",
        "gc_roundtrip_ms",
    )

    for days in windows_days:
        samples = _window_samples(history, current, days)
        paths = sorted(
            {p for sample in samples for p in (sample.get("api") or {})}
            | set((current.get("api") or {}).keys())
        )
        api_baseline: dict[str, Any] = {}
        for path in paths:
            api_baseline[path] = {
                key: _median(
                    [
                        float(sample["api"][path][key])
                        for sample in samples
                        if path in (sample.get("api") or {})
                        and sample["api"][path].get(key) is not None
                    ]
                )
                for key in api_keys
            }
        browser_baseline = {
            key: _median(
                [
                    float(sample["browser"][key])
                    for sample in samples
                    if (sample.get("browser") or {}).get(key) is not None
                ]
            )
            for key in browser_keys
        }
        output[str(days)] = {
            "window_days": days,
            "sample_count": len(samples),
            "mature": len(samples) >= minimum_samples,
            "minimum_samples": minimum_samples,
            "api": api_baseline,
            "browser": browser_baseline,
        }
    return output


def _increase_percent(current: float, baseline: float) -> float | None:
    return None if baseline <= 0 else ((current - baseline) / baseline) * 100


def _drop_percent(current: float, baseline: float) -> float | None:
    return None if baseline <= 0 else ((baseline - current) / baseline) * 100


def detect_regressions(
    current: dict[str, Any],
    baselines: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    latency_limit = float(policy.get("max_latency_increase_percent", 30))
    throughput_limit = float(policy.get("max_throughput_drop_percent", 30))
    error_limit = float(policy.get("max_error_rate_increase_pp", 1))
    browser_limit = float(policy.get("max_browser_metric_increase_percent", 30))

    def add(scope: str, subject: str, metric: str, days: int, current_value: float,
            baseline_value: float, kind: str, delta: float, threshold: float) -> None:
        findings.append(
            {
                "scope": scope,
                "subject": subject,
                "metric": metric,
                "window_days": days,
                "current": round(current_value, 4),
                "baseline": round(baseline_value, 4),
                "delta_percent": round(delta, 2) if kind != "increase_points" else None,
                "delta_points": round(delta, 2) if kind == "increase_points" else None,
                "threshold": threshold,
                "kind": kind,
            }
        )

    for window, baseline_info in baselines.items():
        if not baseline_info.get("mature"):
            continue
        days = int(window)
        for path, metrics in (current.get("api") or {}).items():
            base = (baseline_info.get("api") or {}).get(path) or {}
            for metric in API_HIGHER_WORSE:
                if base.get(metric) is None:
                    continue
                current_value, baseline_value = float(metrics[metric]), float(base[metric])
                delta = _increase_percent(current_value, baseline_value)
                if delta is not None and delta > latency_limit:
                    add("api", path, metric, days, current_value, baseline_value,
                        "increase_percent", delta, latency_limit)
            if base.get("throughput_rps") is not None:
                current_value = float(metrics["throughput_rps"])
                baseline_value = float(base["throughput_rps"])
                delta = _drop_percent(current_value, baseline_value)
                if delta is not None and delta > throughput_limit:
                    add("api", path, "throughput_rps", days, current_value, baseline_value,
                        "drop_percent", delta, throughput_limit)
            if base.get("error_rate_percent") is not None:
                current_value = float(metrics["error_rate_percent"])
                baseline_value = float(base["error_rate_percent"])
                delta = current_value - baseline_value
                if delta > error_limit:
                    add("api", path, "error_rate_percent", days, current_value, baseline_value,
                        "increase_points", delta, error_limit)

        current_browser = current.get("browser") or {}
        baseline_browser = baseline_info.get("browser") or {}
        for metric in BROWSER_HIGHER_WORSE:
            if current_browser.get(metric) is None or baseline_browser.get(metric) is None:
                continue
            current_value = float(current_browser[metric])
            baseline_value = float(baseline_browser[metric])
            delta = _increase_percent(current_value, baseline_value)
            if delta is not None and delta > browser_limit:
                add("browser", "frontend", metric, days, current_value, baseline_value,
                    "increase_percent", delta, browser_limit)
    return findings


def _github_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"ReqSys-Performance-History/{VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"ReqSys-Performance-History/{VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_latest_history(
    repository: str,
    token: str,
    *,
    artifact_name: str,
    retention_days: int,
) -> list[dict[str, Any]]:
    if not repository or not token:
        return []
    name = urllib.parse.quote(artifact_name, safe="")
    url = f"https://api.github.com/repos/{repository}/actions/artifacts?name={name}&per_page=100"
    try:
        payload = _github_json(url, token)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return []
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    artifacts = [
        item
        for item in payload.get("artifacts", [])
        if not item.get("expired")
        and (item.get("workflow_run") or {}).get("head_branch") == "main"
        and item.get("created_at")
        and parse_iso(item["created_at"]) >= cutoff
    ]
    artifacts.sort(key=lambda item: parse_iso(item["created_at"]), reverse=True)
    for artifact in artifacts:
        try:
            raw = _download(str(artifact["archive_download_url"]), token)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                candidates = [n for n in archive.namelist() if n.endswith("performance-history.json")]
                if not candidates:
                    continue
                data = json.loads(archive.read(candidates[0]).decode("utf-8"))
                snapshots = data.get("snapshots")
                if isinstance(snapshots, list):
                    return snapshots
        except (
            KeyError,
            ValueError,
            json.JSONDecodeError,
            zipfile.BadZipFile,
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
        ):
            continue
    return []


def _delta(current: float | None, baseline: float | None, *, lower_worse: bool = False) -> str:
    if current is None or baseline is None or baseline == 0:
        return "—"
    value = ((baseline - current) / baseline) * 100 if lower_worse else ((current - baseline) / baseline) * 100
    return f"{value:+.1f}%"


def _sparkline(values: list[float], width: int = 170, height: int = 40) -> str:
    if not values:
        return "—"
    values = values if len(values) > 1 else [values[0], values[0]]
    low, high = min(values), max(values)
    span = max(high - low, 0.000001)
    points = []
    for index, value in enumerate(values):
        x = (index / (len(values) - 1)) * width
        y = height - ((value - low) / span) * (height - 6) - 3
        points.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="currentColor" '
        'stroke-width="2" vector-effect="non-scaling-stroke"/></svg>'
    )


def render_dashboard(report: dict[str, Any]) -> str:
    current = report["current"]
    b7, b30 = report["baselines"].get("7", {}), report["baselines"].get("30", {})
    regressions = report["regressions"]
    summary = report["summary"]
    snapshots = report["snapshots"]
    status = summary["status"]
    status_class = "ok" if status == "passed" else "warn" if status in {"insufficient_history", "watch"} else "bad"

    endpoint_rows = []
    for path, metrics in (current.get("api") or {}).items():
        base7 = (b7.get("api") or {}).get(path) or {}
        base30 = (b30.get("api") or {}).get(path) or {}
        series = [
            float(item["api"][path]["p95_ms"])
            for item in snapshots
            if path in (item.get("api") or {}) and item["api"][path].get("p95_ms") is not None
        ]
        endpoint_rows.append(
            "<tr>"
            f"<td><code>{html.escape(path)}</code></td>"
            f"<td>{metrics.get('p95_ms', 0):.2f}</td>"
            f"<td>{'—' if base7.get('p95_ms') is None else format(base7['p95_ms'], '.2f')}</td>"
            f"<td>{_delta(metrics.get('p95_ms'), base7.get('p95_ms'))}</td>"
            f"<td>{'—' if base30.get('p95_ms') is None else format(base30['p95_ms'], '.2f')}</td>"
            f"<td>{metrics.get('throughput_rps', 0):.2f}</td>"
            f"<td>{metrics.get('error_rate_percent', 0):.2f}%</td>"
            f"<td>{_sparkline(series[-20:])}</td>"
            "</tr>"
        )

    browser_rows = []
    for metric in BROWSER_HIGHER_WORSE:
        current_value = (current.get("browser") or {}).get(metric)
        base7_value = (b7.get("browser") or {}).get(metric)
        base30_value = (b30.get("browser") or {}).get(metric)
        browser_rows.append(
            "<tr>"
            f"<td><code>{html.escape(metric)}</code></td>"
            f"<td>{'—' if current_value is None else format(current_value, '.2f')}</td>"
            f"<td>{'—' if base7_value is None else format(base7_value, '.2f')}</td>"
            f"<td>{_delta(current_value, base7_value)}</td>"
            f"<td>{'—' if base30_value is None else format(base30_value, '.2f')}</td>"
            "</tr>"
        )

    regression_rows = []
    for item in regressions:
        change = (
            f"{item['delta_percent']:+.1f}%"
            if item.get("delta_percent") is not None
            else f"{item['delta_points']:+.2f} pp"
        )
        regression_rows.append(
            "<tr>"
            f"<td>{html.escape(item['scope'])}</td>"
            f"<td><code>{html.escape(item['subject'])}</code></td>"
            f"<td><code>{html.escape(item['metric'])}</code></td>"
            f"<td>{item['window_days']}d</td>"
            f"<td>{item['current']:.2f}</td>"
            f"<td>{item['baseline']:.2f}</td>"
            f"<td>{change}</td>"
            "</tr>"
        )
    if not regression_rows:
        regression_rows.append('<tr><td colspan="7">Nenhuma regressão madura detectada.</td></tr>')

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ReqSys Performance History</title>
<style>:root{{color-scheme:dark;font-family:Inter,Segoe UI,Arial,sans-serif}}body{{margin:0;background:#0b1220;color:#e5e7eb}}main{{max-width:1280px;margin:auto;padding:24px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0}}.card{{background:#111827;border:1px solid #334155;border-radius:12px;padding:16px}}.value{{font-size:1.55rem;font-weight:700}}.ok{{color:#4ade80}}.warn{{color:#facc15}}.bad{{color:#f87171}}table{{width:100%;border-collapse:collapse;background:#111827;margin:10px 0 24px}}th,td{{padding:10px;border:1px solid #334155;text-align:left}}th{{background:#172033}}code,svg{{color:#7dd3fc}}small{{color:#94a3b8}}</style></head><body><main>
<h1>ReqSys — Performance 7/30 dias</h1><small>Gerado em {html.escape(report['generated_at'])} · run {html.escape(str(current.get('run_id','')))} · SHA {html.escape(str(current.get('head_sha',''))[:12])}</small>
<section class="cards"><div class="card"><div>Status</div><div class="value {status_class}">{html.escape(status)}</div></div><div class="card"><div>Amostras rolling</div><div class="value">{summary['samples_total']}</div></div><div class="card"><div>Baseline 7d</div><div class="value">{b7.get('sample_count',0)}/{b7.get('minimum_samples',0)}</div></div><div class="card"><div>Baseline 30d</div><div class="value">{b30.get('sample_count',0)}/{b30.get('minimum_samples',0)}</div></div><div class="card"><div>Regressões</div><div class="value {'warn' if regressions else 'ok'}">{len(regressions)}</div></div></section>
<h2>Endpoints</h2><table><thead><tr><th>Endpoint</th><th>p95 atual</th><th>p95 7d</th><th>Δ 7d</th><th>p95 30d</th><th>RPS</th><th>Erro</th><th>Tendência</th></tr></thead><tbody>{''.join(endpoint_rows)}</tbody></table>
<h2>Runtime JavaScript</h2><table><thead><tr><th>Métrica</th><th>Atual</th><th>Mediana 7d</th><th>Δ 7d</th><th>Mediana 30d</th></tr></thead><tbody>{''.join(browser_rows)}</tbody></table>
<h2>Regressões maduras</h2><table><thead><tr><th>Escopo</th><th>Alvo</th><th>Métrica</th><th>Janela</th><th>Atual</th><th>Baseline</th><th>Regressão</th></tr></thead><tbody>{''.join(regression_rows)}</tbody></table>
<p><small>Baseline usa mediana e exclui a amostra atual. Regressão relativa isolada é watch quando block_on_single_regression=false; bloqueio sustentado é tratado pelo Performance SLO Error Budget Gate.</small></p></main></body></html>"""


def build_report(
    *,
    policy: dict[str, Any],
    history: list[dict[str, Any]],
    current: dict[str, Any],
) -> dict[str, Any]:
    history_policy = policy.get("history") or {}
    retention_days = int(history_policy.get("retention_days", 45))
    windows_days = [int(value) for value in history_policy.get("windows_days", [7, 30])]
    minimum_samples = int(history_policy.get("minimum_baseline_samples", 5))
    merged = merge_and_prune(history, current, retention_days=retention_days)
    baselines = build_baselines(
        merged,
        current,
        windows_days=windows_days,
        minimum_samples=minimum_samples,
    )
    regressions = detect_regressions(
        current,
        baselines,
        history_policy.get("regression") or {},
    )
    mature = [int(key) for key, value in baselines.items() if value.get("mature")]
    block_single = bool(history_policy.get("block_on_single_regression", True))
    if regressions:
        status = "blocked" if block_single else "watch"
    else:
        status = "passed" if mature else "insufficient_history"
    return {
        "schema_version": "1.0.0",
        "history_version": VERSION,
        "contract": "reqsys-performance-history-7d-30d",
        "policy_version": policy.get("policy_version", "unknown"),
        "generated_at": iso_utc(datetime.now(UTC)),
        "summary": {
            "status": status,
            "samples_total": len(merged),
            "mature_windows": mature,
            "regressions_total": len(regressions),
            "minimum_baseline_samples": minimum_samples,
            "retention_days": retention_days,
            "block_on_single_regression": block_single,
        },
        "current": current,
        "baselines": baselines,
        "regressions": regressions,
        "snapshots": merged,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ReqSys performance history 7/30d")
    parser.add_argument("--current-api", type=Path, required=True)
    parser.add_argument("--current-browser", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config/runtime-performance-budgets.json"))
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""))
    parser.add_argument("--artifact-name", default=DEFAULT_ARTIFACT_NAME)
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--head-sha", default=os.getenv("GITHUB_SHA", "unknown"))
    parser.add_argument("--head-branch", default=os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME", "unknown"))
    parser.add_argument("--mode", default="unknown")
    parser.add_argument("--output-json", type=Path, default=Path("artifacts/performance/performance-history.json"))
    parser.add_argument("--output-dashboard", type=Path, default=Path("artifacts/performance/performance-dashboard.html"))
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--history-input", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        api = json.loads(args.current_api.read_text(encoding="utf-8"))
        browser = json.loads(args.current_browser.read_text(encoding="utf-8"))
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        retention_days = int((policy.get("history") or {}).get("retention_days", 45))
        if args.history_input:
            payload = json.loads(args.history_input.read_text(encoding="utf-8"))
            previous = payload.get("snapshots", payload)
            if not isinstance(previous, list):
                raise ValueError("history-input deve conter lista ou objeto com snapshots")
        else:
            previous = fetch_latest_history(
                args.repository,
                args.token,
                artifact_name=args.artifact_name,
                retention_days=retention_days,
            )
        current = snapshot_from_reports(
            api,
            browser,
            run_id=args.run_id,
            event_name=args.event_name,
            head_sha=args.head_sha,
            head_branch=args.head_branch,
            mode=args.mode,
        )
        report = build_report(policy=policy, history=previous, current=current)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_dashboard.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.output_dashboard.write_text(render_dashboard(report), encoding="utf-8")
        print(json.dumps(report["summary"], ensure_ascii=False))
        return 1 if args.strict and report["summary"]["status"] == "blocked" else 0
    except Exception as exc:
        print(f"performance_history_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
