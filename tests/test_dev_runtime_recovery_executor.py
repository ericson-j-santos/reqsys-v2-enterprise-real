import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

import scripts.dev_runtime_recovery as recovery
from scripts.dev_runtime_recovery import (
    HOST,
    PROJECT,
    RecoveryError,
    Result,
    capture,
    deploy_check,
    prepare,
    rollback,
    validate,
)

IMAGE = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
OLD = "5" * 40


def test_fixed_runtime_root_matches_governed_dev_worktree():
    assert str(recovery.ROOT) == r"C:\dev\chatgpt-workers\wt-pc24x7-public-dev-governed"


class Fake:
    def __init__(
        self,
        root,
        fail=None,
        duplicate=False,
        tags=None,
        config_orders=None,
        env_orders=None,
        sql_output=None,
        sql_timeout=False,
    ):
        self.root = root
        self.fail = fail
        self.duplicate = duplicate
        self.tags = tags or {}
        self.calls = []
        self.config_orders = config_orders or {}
        self.env_orders = env_orders or {}
        self.sql_output = sql_output
        self.sql_timeout = sql_timeout

    def run(self, argv, timeout=30, input_text=None):
        self.calls.append((tuple(argv), input_text))
        joined = " ".join(argv)
        if self.fail and self.fail in joined:
            return Result(7, "", "password=must-not-escape")
        if argv[:2] == ("docker", "ps"):
            service = next(
                x.rsplit("=", 1)[-1] for x in argv if "compose.service=" in x
            )
            return Result(
                0, f"id-{service}\n" + ("duplicate\n" if self.duplicate else ""), ""
            )
        if argv[:2] == ("docker", "inspect"):
            service = argv[-1].replace("id-", "")
            configs = self.config_orders.get(service, [self.root / "compose.yaml"])
            envs = self.env_orders.get(service, [self.root / "runtime.env"])
            labels = {
                "com.docker.compose.project": PROJECT,
                "com.docker.compose.service": service,
                "com.docker.compose.project.working_dir": str(self.root),
                "com.docker.compose.project.config_files": ",".join(map(str, configs)),
                "com.docker.compose.project.environment_file": ",".join(map(str, envs)),
            }
            return Result(
                0, json.dumps([{"Image": IMAGE, "Config": {"Labels": labels}}]), ""
            )
        if argv[:3] == ("docker", "image", "inspect"):
            target = argv[3]
            if target.startswith("reqsys-rollback/"):
                if target not in self.tags:
                    return Result(1, "", "")
                return Result(0, json.dumps([{"Id": self.tags[target]}]), "")
            return Result(0, "[]", "")
        if argv[:3] == ("docker", "image", "tag"):
            self.tags[argv[4]] = argv[3]
            return Result(0, "", "")
        if argv[:3] == ("docker", "exec", "-i"):
            assert "SessionLocal" in input_text and 'text("SELECT 1")' in input_text
            if self.sql_timeout:
                raise subprocess.TimeoutExpired(argv, timeout)
            if self.sql_output is not None:
                return self.sql_output
            return Result(0, '{"category":"ok","database_ok":true}', "")
        return Result(0, "[]", "")


@pytest.fixture
def root(tmp_path):
    (tmp_path / "compose.yaml").write_text("services: {}\n")
    (tmp_path / "z-base.yaml").write_text("services: {}\n")
    (tmp_path / "a-override.yaml").write_text("services: {}\n")
    (tmp_path / "runtime.env").write_text("SECRET=not-captured\n")
    (tmp_path / "second.env").write_text("OTHER=not-captured\n")
    return tmp_path


def captured(root, runner=None):
    runner = runner or Fake(root)
    return capture(runner, root=root, identity_probe=lambda: OLD, hostname=HOST)


def prepared(root, runner=None):
    runner = runner or Fake(root)
    m = captured(root, runner)
    return prepare(m, runner, m["fingerprint"], root)


def test_capture_sanitized_scope_and_cardinality(root):
    m = captured(root)
    assert "SECRET=" not in json.dumps(m)
    assert m["runtime_sha"] == OLD
    with pytest.raises(RecoveryError, match="host_identity_refused"):
        capture(Fake(root), root=root, identity_probe=lambda: OLD, hostname="prod")
    with pytest.raises(RecoveryError, match="container_cardinality"):
        captured(root, Fake(root, duplicate=True))


def test_capture_preserves_non_alphabetic_order_and_rejects_divergence(root):
    order = [root / "z-base.yaml", root / "a-override.yaml"]
    env = [root / "second.env", root / "runtime.env"]
    runner = Fake(
        root,
        config_orders={s: order for s in recovery.SERVICES},
        env_orders={s: env for s in recovery.SERVICES},
    )
    m = captured(root, runner)
    assert [x["relative_path"] for x in m["compose_files"]] == [
        "z-base.yaml",
        "a-override.yaml",
    ]
    assert [x["relative_path"] for x in m["environment_files"]] == [
        "second.env",
        "runtime.env",
    ]
    bad = Fake(
        root,
        config_orders={"api": order, "frontend": list(reversed(order)), "nginx": order},
    )
    with pytest.raises(RecoveryError, match="compose_config_order_mismatch"):
        captured(root, bad)
    bad_env = Fake(
        root, env_orders={"api": env, "frontend": list(reversed(env)), "nginx": env}
    )
    with pytest.raises(RecoveryError, match="environment_file_order_mismatch"):
        captured(root, bad_env)


def test_prepare_tags_images_readback_and_idempotence(root):
    runner = Fake(root)
    m = captured(root, runner)
    p1 = prepare(m, runner, m["fingerprint"], root)
    p2 = prepare(m, runner, m["fingerprint"], root)
    assert p1 == p2 and (root / p1["rollback_override"]["relative_path"]).exists()
    validate(p1, runner, p1["fingerprint"], root, True)


def test_tag_collision_refused(root):
    runner = Fake(root, tags={recovery.rollback_tag("api", OLD): OTHER})
    m = captured(root, runner)
    with pytest.raises(RecoveryError, match="rollback_tag_collision"):
        prepare(m, runner, m["fingerprint"], root)


def test_external_fingerprint_blocks_resealed_tamper(root):
    runner = Fake(root)
    m = captured(root, runner)
    external = m["fingerprint"]
    m["runtime_sha"] = "6" * 40
    m["fingerprint"] = recovery.fingerprint(
        {k: v for k, v in m.items() if k != "fingerprint"}
    )
    with pytest.raises(RecoveryError, match="external_fingerprint_mismatch"):
        validate(m, runner, external, root)


def test_lexical_traversal_and_internal_link_refused(root, monkeypatch):
    outside = root.parent / "outside"
    outside.write_text("x")
    with pytest.raises(RecoveryError, match="external_path_refused|traversal_refused"):
        recovery.safe_relative(root / ".." / "outside", root)
    link = root / "link"
    link.write_text("x")
    real = recovery._reparse
    monkeypatch.setattr(recovery, "_reparse", lambda p: True if p == link else real(p))
    with pytest.raises(RecoveryError, match="link_refused"):
        recovery.safe_relative(link, root)


def test_root_reparse_refused(root, monkeypatch):
    real = recovery._reparse
    monkeypatch.setattr(
        recovery,
        "_reparse",
        lambda p: True if p == Path(os.path.abspath(root)) else real(p),
    )
    with pytest.raises(RecoveryError, match="root_reparse_refused"):
        recovery.safe_relative(root / "compose.yaml", root)


def test_legacy_probe_is_stdin_and_not_new_module(root):
    runner = Fake(root)
    p = prepared(root, runner)
    runner.calls.clear()
    rollback(
        p, runner, p["fingerprint"], root, identity_probe=lambda: OLD, hostname=HOST
    )
    call = next(x for x in runner.calls if x[0][:3] == ("docker", "exec", "-i"))
    assert call[0][-3:] == ("python", "-B", "-")
    assert "probe_dev_database_readonly" not in call[1]


def test_live_guard_runs_before_each_mutation(root):
    runner = Fake(root)
    p = prepared(root, runner)
    runner.calls.clear()
    rollback(
        p, runner, p["fingerprint"], root, identity_probe=lambda: OLD, hostname=HOST
    )
    commands = [" ".join(x[0]) for x in runner.calls]
    ups = [i for i, x in enumerate(commands) if "force-recreate" in x]
    for index in ups:
        assert any(
            "docker inspect id-api" in x for x in commands[max(0, index - 20) : index]
        )


def test_compose_argv_preserves_env_then_file_order(root):
    order = [root / "z-base.yaml", root / "a-override.yaml"]
    env = [root / "second.env", root / "runtime.env"]
    runner = Fake(
        root,
        config_orders={s: order for s in recovery.SERVICES},
        env_orders={s: env for s in recovery.SERVICES},
    )
    p = prepared(root, runner)
    runner.calls.clear()
    rollback(
        p, runner, p["fingerprint"], root, identity_probe=lambda: OLD, hostname=HOST
    )
    argv = next(
        x[0]
        for x in runner.calls
        if "--force-recreate" in x[0] and x[0][-2:] == ("api", "frontend")
    )
    prefix = argv[: argv.index("up")]
    assert prefix == (
        "docker",
        "compose",
        "--project-name",
        PROJECT,
        "--env-file",
        str(root / "second.env"),
        "--env-file",
        str(root / "runtime.env"),
        "--file",
        str(root / "z-base.yaml"),
        "--file",
        str(root / "a-override.yaml"),
        "--file",
        str(root / p["rollback_override"]["relative_path"]),
    )


def test_wait_succeeds_after_transient_states(root):
    runner = Fake(root)
    p = prepared(root, runner)
    values = iter([OLD, RecoveryError("starting"), "6" * 40, OLD, OLD, OLD])
    ticks = [0]

    def probe():
        value = next(values, OLD)
        if isinstance(value, Exception):
            raise value
        return value

    def clock():
        return ticks[0]

    def sleep(value):
        ticks[0] += value

    assert rollback(
        p,
        runner,
        p["fingerprint"],
        root,
        identity_probe=probe,
        hostname=HOST,
        wait_timeout=10,
        wait_interval=1,
        clock=clock,
        sleeper=sleep,
    )["rollback_ok"]
    assert ticks[0] >= 2


def test_wait_timeout_is_bounded_and_sanitized(root):
    runner = Fake(root)
    p = prepared(root, runner)
    ticks = [0]

    def clock():
        return ticks[0]

    def sleep(value):
        ticks[0] += value

    with pytest.raises(RecoveryError, match="rollback_failed:readiness_timeout") as exc:
        rollback(
            p,
            runner,
            p["fingerprint"],
            root,
            identity_probe=lambda: "6" * 40,
            hostname=HOST,
            wait_timeout=3,
            wait_interval=1,
            clock=clock,
            sleeper=sleep,
        )
    assert ticks[0] == 3 and "password" not in str(exc.value)


def runtime_result(sha=OLD):
    return {
        "identity_validated": True,
        "routes": {
            "/api/runtime/build-info": {"build_sha": sha},
            "/api/runtime/health": {"status": "healthy"},
            "/api/runtime/readiness": {"status": "healthy"},
            "/api/runtime/liveness": {"alive": True},
        },
    }


def test_real_probe_error_is_retried_then_converges(root, monkeypatch):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    values = iter(
        [
            identity.ProbeError("transport_error"),
            identity.ProbeError("http_error"),
            runtime_result(),
        ]
    )
    ticks = [0]

    def run(_):
        value = next(values, runtime_result())
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(identity, "run", run)
    runner = Fake(root)
    result = recovery.wait_live(
        runner,
        OLD,
        root,
        recovery.observe_identity,
        HOST,
        5,
        1,
        lambda: ticks[0],
        lambda value: ticks.__setitem__(0, ticks[0] + value),
    )
    assert result["runtime_sha"] == OLD and ticks[0] == 2


def test_real_probe_error_permanent_reaches_bounded_timeout(root, monkeypatch):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    monkeypatch.setattr(
        identity,
        "run",
        lambda _: (_ for _ in ()).throw(
            identity.ProbeError("transport_error:secret=hidden")
        ),
    )
    ticks = [0]
    with pytest.raises(RecoveryError, match="readiness_timeout") as exc:
        recovery.wait_live(
            Fake(root),
            OLD,
            root,
            recovery.observe_identity,
            HOST,
            3,
            1,
            lambda: ticks[0],
            lambda value: ticks.__setitem__(0, ticks[0] + value),
        )
    assert ticks[0] == 3 and "secret" not in str(exc.value)


def test_liveness_contract_accepts_two_documented_forms_and_rejects_contradictions(
    monkeypatch,
):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    for live in ({"alive": True}, {"status": "alive"}):
        payload = runtime_result()
        payload["routes"]["/api/runtime/liveness"] = live
        monkeypatch.setattr(identity, "run", lambda _, payload=payload: payload)
        assert recovery.observe_identity() == OLD
    for live in ({"alive": False}, {"status": "dead"}, {}):
        payload = runtime_result()
        payload["routes"]["/api/runtime/liveness"] = live
        monkeypatch.setattr(identity, "run", lambda _, payload=payload: payload)
        with pytest.raises(RecoveryError, match="live_liveness_invalid"):
            recovery.observe_identity()


def integrated_probe_result(liveness):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    class Response:
        status = 200

        def __init__(self, payload):
            self.payload = json.dumps({"data": payload}).encode()

        def read(self, _):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Opener:
        def open(self, request, timeout):
            return Response(values[request.full_url])

    base = "http://127.0.0.1:8210"
    common = {
        "service": "reqsys-api",
        "version": "3.1.0",
        "environment": "desenvolvimento",
    }
    values = {
        base + identity.ROUTES[0]: common,
        base + identity.ROUTES[1]: {**common, "status": "healthy"},
        base + identity.ROUTES[2]: {**common, "status": "healthy"},
        base + identity.ROUTES[3]: {**common, **liveness},
        base + identity.ROUTES[4]: {**common, "build_sha": OLD},
        base + identity.ROUTES[5]: {**common, "dependencies": []},
    }
    return identity.run(OLD, Opener())


def test_integrated_probe_to_recovery_liveness_contract(monkeypatch):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    invalid = (
        {"alive": False, "status": "alive"},
        {"alive": True, "status": "dead"},
        {"alive": 1},
        {"alive": "true"},
        {"alive": None},
        {"alive": True, "status": "invalid"},
        {},
    )
    valid_results = [
        integrated_probe_result(live) for live in ({"alive": True}, {"status": "alive"})
    ]
    invalid_results = [integrated_probe_result(live) for live in invalid]
    for result in valid_results:
        monkeypatch.setattr(identity, "run", lambda _, result=result: result)
        assert recovery.observe_identity() == OLD
    for result in invalid_results:
        monkeypatch.setattr(identity, "run", lambda _, result=result: result)
        with pytest.raises(RecoveryError, match="live_liveness_invalid"):
            recovery.observe_identity()


@pytest.mark.parametrize(
    "alive_present,alive",
    [
        (False, None),
        (True, True),
        (True, False),
        (True, 0),
        (True, 1),
        (True, "true"),
        (True, None),
        (True, ["x"]),
        (True, {"secret_alive": "hidden"}),
    ],
)
@pytest.mark.parametrize(
    "status_present,status",
    [
        (False, None),
        (True, "alive"),
        (True, "healthy"),
        (True, "ok"),
        (True, "dead"),
        (True, ""),
        (True, None),
        (True, 1),
        (True, True),
        (True, ["x"]),
        (True, {"secret_status": "hidden"}),
    ],
)
def test_integrated_liveness_cartesian_contract(
    monkeypatch, alive_present, alive, status_present, status
):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    live = {}
    if alive_present:
        live["alive"] = alive
    if status_present:
        live["status"] = status
    result = integrated_probe_result(live)
    normalized = result["routes"][identity.ROUTES[3]]
    monkeypatch.setattr(identity, "run", lambda _, result=result: result)
    alive_valid = alive_present and type(alive) is bool and alive is True
    status_valid = (
        status_present
        and isinstance(status, str)
        and status.casefold() in {"alive", "healthy", "ok"}
    )
    all_present_valid = (not alive_present or alive_valid) and (
        not status_present or status_valid
    )
    should_accept = all_present_valid and (alive_valid or status_valid)
    if should_accept:
        assert recovery.observe_identity() == OLD
    else:
        with pytest.raises(RecoveryError, match="live_liveness_invalid"):
            recovery.observe_identity()
    rendered = json.dumps(normalized)
    assert "secret_alive" not in rendered and "secret_status" not in rendered
    if alive_present and type(alive) is not bool:
        assert (
            normalized.get("alive_invalid_type") is True and "alive" not in normalized
        )
    if status_present and not isinstance(status, str):
        assert (
            normalized.get("status_invalid_type") is True and "status" not in normalized
        )


def test_health_and_readiness_invalid_status_markers_are_rejected(monkeypatch):
    import scripts.probe_pc24x7_dev_runtime_identity as identity

    routes = (identity.ROUTES[1], identity.ROUTES[2])
    results = [integrated_probe_result({"alive": True}) for _ in routes]
    for route, result in zip(routes, results):
        result["routes"][route].pop("status", None)
        result["routes"][route]["status_invalid_type"] = True
        monkeypatch.setattr(identity, "run", lambda _, result=result: result)
        with pytest.raises(RecoveryError, match="live_readiness_invalid"):
            recovery.observe_identity()


def assert_read_only(runner):
    commands = [x[0] for x in runner.calls]
    assert not any(x[:2] == ("docker", "compose") for x in commands)
    assert not any(x[:3] == ("docker", "image", "tag") for x in commands)
    assert not any(
        any(token in x for token in ("restart", "stop", "rm", "up", "create"))
        for x in commands
    )


def test_deploy_check_positive_is_read_only(root):
    before = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }
    runner = Fake(root)
    result = deploy_check(OLD, runner, root, identity_probe=lambda: OLD, hostname=HOST)
    after = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }
    assert result == {
        "deploy_check_ok": True,
        "environment": "dev",
        "project": PROJECT,
        "runtime_sha": OLD,
        "database_ok": True,
    }
    assert before == after
    assert_read_only(runner)


def test_deploy_check_sql_error_and_malformed_json(root):
    for response, category in (
        (
            Result(
                1, '{"category":"query_failed","database_ok":false}', "secret=hidden"
            ),
            "database_probe_failed",
        ),
        (Result(0, "not-json", ""), "database_probe_invalid"),
    ):
        runner = Fake(root, sql_output=response)
        with pytest.raises(RecoveryError, match=category) as exc:
            deploy_check(OLD, runner, root, identity_probe=lambda: OLD, hostname=HOST)
        assert "secret" not in str(exc.value)
        assert_read_only(runner)


def test_deploy_check_sql_timeout(root):
    runner = Fake(root, sql_timeout=True)
    with pytest.raises(RecoveryError, match="database_probe_timeout"):
        deploy_check(OLD, runner, root, identity_probe=lambda: OLD, hostname=HOST)
    assert_read_only(runner)


def test_deploy_check_sha_mismatch_is_bounded(root):
    runner = Fake(root)
    ticks = [0]
    with pytest.raises(RecoveryError, match="^deploy_readiness_sha_mismatch$"):
        deploy_check(
            "6" * 40,
            runner,
            root,
            identity_probe=lambda: OLD,
            hostname=HOST,
            wait_timeout=2,
            wait_interval=1,
            clock=lambda: ticks[0],
            sleeper=lambda value: ticks.__setitem__(0, ticks[0] + value),
        )
    assert ticks[0] == 2
    assert_read_only(runner)




@pytest.mark.parametrize(
    ("upstream_error", "expected_category"),
    [
        ("live_probe_unavailable:private-url", "deploy_readiness_probe_unavailable"),
        ("live_readiness_invalid:secret-content", "deploy_readiness_unhealthy"),
        ("unrecognized_error:password=hidden", "deploy_readiness_unknown"),
    ],
)
def test_deploy_check_timeout_preserves_allowlisted_reason(
    root, upstream_error, expected_category
):
    runner = Fake(root)
    ticks = [0]

    def unavailable():
        raise RecoveryError(upstream_error)

    with pytest.raises(RecoveryError, match=f"^{expected_category}$") as exc:
        deploy_check(
            OLD, runner, root, identity_probe=unavailable, hostname=HOST,
            wait_timeout=2, wait_interval=1,
            clock=lambda: ticks[0],
            sleeper=lambda value: ticks.__setitem__(0, ticks[0] + value),
        )
    assert ticks[0] == 2
    assert "password=" not in str(exc.value)
    assert "private-url" not in str(exc.value)
    assert_read_only(runner)


@pytest.mark.parametrize(
    ("upstream_error", "expected_category"),
    [
        ("host_identity_refused", "deploy_readiness_scope_invalid"),
        ("live_probe_source_unavailable", "deploy_readiness_probe_invalid"),
    ],
)
def test_deploy_check_static_readiness_failure_fails_fast(
    root, upstream_error, expected_category
):
    runner = Fake(root)
    ticks = [0]

    def unavailable():
        raise RecoveryError(upstream_error)

    with pytest.raises(RecoveryError, match=f"^{expected_category}$"):
        deploy_check(
            OLD, runner, root, identity_probe=unavailable, hostname=HOST,
            wait_timeout=90, wait_interval=1,
            clock=lambda: ticks[0],
            sleeper=lambda value: ticks.__setitem__(0, ticks[0] + value),
        )
    assert ticks[0] == 0
    assert_read_only(runner)


def test_deploy_check_docker_container_unavailable_is_typed(root):
    runner = Fake(root, fail="docker ps")
    ticks = [0]
    with pytest.raises(RecoveryError, match="^deploy_readiness_container_unavailable$"):
        deploy_check(
            OLD, runner, root, identity_probe=lambda: OLD, hostname=HOST,
            wait_timeout=2, wait_interval=1,
            clock=lambda: ticks[0],
            sleeper=lambda value: ticks.__setitem__(0, ticks[0] + value),
        )
    assert ticks[0] == 2
    assert_read_only(runner)


def test_deploy_check_recovers_from_transient_probe_failure(root):
    runner = Fake(root)
    ticks = [0]
    attempts = [0]

    def temporary_unavailability():
        attempts[0] += 1
        if attempts[0] == 1:
            raise RecoveryError("live_probe_unavailable:private-detail")
        return OLD

    result = deploy_check(
        OLD, runner, root, identity_probe=temporary_unavailability, hostname=HOST,
        wait_timeout=3, wait_interval=1,
        clock=lambda: ticks[0],
        sleeper=lambda value: ticks.__setitem__(0, ticks[0] + value),
    )
    assert result["deploy_check_ok"] is True
    assert result["runtime_sha"] == OLD
    assert attempts[0] == 2 and ticks[0] == 1
    assert_read_only(runner)


def test_durable_override_supports_next_capture(root):
    runner = Fake(root)
    p = prepared(root, runner)
    rollback(
        p, runner, p["fingerprint"], root, identity_probe=lambda: OLD, hostname=HOST
    )
    override = root / p["rollback_override"]["relative_path"]
    assert override.exists()

    class After(Fake):
        def run(self, argv, timeout=30, input_text=None):
            r = super().run(argv, timeout, input_text)
            if argv[:2] == ("docker", "inspect"):
                d = json.loads(r.stdout)
                d[0]["Config"]["Labels"]["com.docker.compose.project.config_files"] += (
                    "," + str(override)
                )
                return Result(0, json.dumps(d), "")
            return r

    assert any(
        x["relative_path"] == p["rollback_override"]["relative_path"]
        for x in captured(root, After(root))["compose_files"]
    )


@pytest.mark.parametrize(
    "phase", ["force-recreate api frontend", "docker exec -i", "force-recreate nginx"]
)
def test_phase_failures_sanitized(root, phase):
    runner = Fake(root)
    p = prepared(root, runner)
    runner.fail = phase
    with pytest.raises(RecoveryError, match="rollback_failed") as exc:
        rollback(
            p, runner, p["fingerprint"], root, identity_probe=lambda: OLD, hostname=HOST
        )
    assert "password" not in str(exc.value)


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (FileNotFoundError("DETAIL_NOT_PUBLIC"), "runtime_file_missing"),
        (PermissionError("DETAIL_NOT_PUBLIC"), "runtime_permission_denied"),
        (ImportError("DETAIL_NOT_PUBLIC"), "runtime_dependency_missing"),
        (OSError("DETAIL_NOT_PUBLIC"), "runtime_os_error"),
        (KeyError("DETAIL_NOT_PUBLIC"), "runtime_payload_invalid"),
        (TypeError("DETAIL_NOT_PUBLIC"), "runtime_payload_invalid"),
        (ValueError("DETAIL_NOT_PUBLIC"), "runtime_payload_invalid"),
        (AttributeError("DETAIL_NOT_PUBLIC"), "runtime_payload_invalid"),
        (IndexError("DETAIL_NOT_PUBLIC"), "runtime_payload_invalid"),
        (subprocess.TimeoutExpired(["DETAIL_NOT_PUBLIC"], 3),
         "runtime_subprocess_timeout"),
    ],
)
def test_deploy_check_cli_sanitizes_expected_runtime_errors(
    failure, reason, monkeypatch, capsys
):
    def failed_check(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(recovery, "deploy_check", failed_check)
    monkeypatch.setattr(
        sys, "argv",
        ["dev_runtime_recovery.py", "deploy-check", "--expected-sha", OLD],
    )
    assert recovery.main() == 1
    out = capsys.readouterr()
    assert out.err == ""
    assert len(out.out.strip().splitlines()) == 1
    assert json.loads(out.out) == {"ok": False, "category": reason}
    assert "DETAIL_NOT_PUBLIC" not in out.out + out.err


def test_deploy_check_cli_positive_emits_existing_success_contract(
    monkeypatch, capsys
):
    def succeeded(*_args, **_kwargs):
        return {
            "deploy_check_ok": True, "environment": "dev",
            "project": PROJECT, "runtime_sha": OLD, "database_ok": True,
        }

    monkeypatch.setattr(recovery, "deploy_check", succeeded)
    monkeypatch.setattr(
        sys, "argv",
        ["dev_runtime_recovery.py", "deploy-check", "--expected-sha", OLD],
    )
    assert recovery.main() == 0
    result = capsys.readouterr()
    assert result.err == ""
    assert json.loads(result.out)["runtime_sha"] == OLD


def test_deploy_check_direct_probe_loads_fixed_sibling_not_import_shadow(monkeypatch):
    shadow = ModuleType("probe_pc24x7_dev_runtime_identity")
    shadow.ProbeError = RuntimeError
    shadow.run = lambda _: "invalid shadow"
    monkeypatch.setitem(sys.modules, shadow.__name__, shadow)
    monkeypatch.setattr(recovery, "__package__", None)
    probe_error, run = recovery._load_identity_probe()
    assert probe_error.__name__ == "ProbeError"
    assert run.__module__ == "_reqsys_fixed_pc24x7_probe"
    assert run is not shadow.run
    second_error, second_run = recovery._load_identity_probe()
    assert second_error.__name__ == probe_error.__name__
    assert second_run.__module__ == run.__module__


def test_deploy_check_direct_probe_validates_runtime_without_sys_path(monkeypatch, tmp_path):
    script = tmp_path / "dev_runtime_recovery.py"
    probe = tmp_path / "probe_pc24x7_dev_runtime_identity.py"
    probe.write_text(
        "class ProbeError(RuntimeError): pass\n"
        + f"def run(_): return {runtime_result()!r}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(recovery, "__package__", None)
    monkeypatch.setattr(recovery, "__file__", str(script))
    assert recovery.observe_identity() == OLD


def test_deploy_check_direct_probe_missing_sibling_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(recovery, "__package__", None)
    monkeypatch.setattr(recovery, "__file__", str(tmp_path / "dev_runtime_recovery.py"))
    with pytest.raises(RecoveryError, match="^live_probe_source_unavailable$"):
        recovery._load_identity_probe()


def test_deploy_check_direct_probe_malformed_sibling_fails_closed(monkeypatch, tmp_path):
    probe = tmp_path / "probe_pc24x7_dev_runtime_identity.py"
    probe.write_text("ProbeError = object\nrun = None\n", encoding="utf-8")
    monkeypatch.setattr(recovery, "__package__", None)
    monkeypatch.setattr(recovery, "__file__", str(tmp_path / "dev_runtime_recovery.py"))
    with pytest.raises(RecoveryError, match="^live_probe_contract_invalid$"):
        recovery._load_identity_probe()
