 isinstance(pid, int) and pid > 0]
    if len(matching) != len(raw_matching) or len(unresolved) != len(raw_unresolved):
        _fail("listener_process_probe_invalid")
    if unresolved:
        _fail("listener_process_identity_unresolved")
    if len(matching) > 1:
        _fail("duplicate_target_listener")
    observed: list[dict[str, Any]] = []
    if isinstance(raw_observed, list):
        for entry in raw_observed:
            if not isinstance(entry, Mapping):
                _fail("listener_process_probe_invalid")
            pid = entry.get("pid")
            path = entry.get("path")
            if not isinstance(pid, int) or pid <= 0 or not isinstance(path, str) or not path:
                _fail("listener_process_probe_invalid")
            observed.append({"pid": pid, "executable_path": str(Path(path).resolve())})
    return {
        "expected_executable": expected,
        "matching_pids": matching,
        "unresolved_pids": unresolved,
        "observed": observed,
    }


def _base_evidence(
    *,
    mode: str,
    runner_home: Path | None,
    source_host: str | None,
    source_runner_name: str | None,
    repository: str | None,
) -> dict[str, Any]:
    target_home = str(runner_home.resolve()) if runner_home is not None else ""
    return {
        "schema_version": "1",
        "generated_at_utc": now_iso(),
        "ok": False,
        "result": "DESKTOP_DEDICATED_LISTENER_RECOVERY_BLOCKED",
        "mode": mode,
        "source_host": source_host or "",
        "source_runner_name": source_runner_name or "",
        "source_runner_id": SOURCE_RUNNER_ID,
        "source_repository": repository or SOURCE_REPOSITORY,
        "target_repository": TARGET_REPOSITORY,
        "target_runner_id": TARGET_RUNNER_ID,
        "target_runner_name": TARGET_RUNNER_NAME,
        "target_runner_home": target_home,
        "target_listener_executable": (
            str((runner_home / "bin" / LISTENER_NAME).resolve()) if runner_home else ""
        ),
        "target_listener_version": "",
        "target_listener_pids": [],
        "observed_listener_processes": [],
        "target_registry_status": "",
        "target_registry_busy": False,
        "action": "none",
        "action_count": 0,
        "identity_verified": False,
        "process_arguments_observed": False,
        "credentials_observed": False,
        "raw_logs_read": False,
        "remote_shell_used": False,
        "registration_mutated": False,
        "labels_mutated": False,
        "services_mutated": False,
        "tasks_mutated": False,
        "firewall_mutated": False,
        "acl_mutated": False,
        "safe_directory_mutated": False,
        "activation_script_called": False,
        "production_touched": False,
        "block_reason": "",
    }


def _write(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dict(payload)


def _collect(
    *,
    runner_home: Path,
    host: str | None,
    platform: str | None,
    runner_name: str | None,
    repository: str | None,
    identity_reader: IdentityReader,
    snapshot_reader: SnapshotReader,
    version_reader: VersionReader,
) -> dict[str, Any]:
    actual_host = host or socket.gethostname()
    actual_platform = platform or os.name
    actual_runner_name = runner_name if runner_name is not None else os.environ.get("RUNNER_NAME", "")
    actual_repository = repository if repository is not None else os.environ.get("GITHUB_REPOSITORY", "")
    if actual_platform != "nt":
        _fail("windows_required")
    if actual_host.casefold() != SOURCE_HOST.casefold():
        _fail("source_host_mismatch")
    if actual_runner_name.casefold() != SOURCE_RUNNER_NAME.casefold():
        _fail("source_runner_name_mismatch")
    if actual_repository != SOURCE_REPOSITORY:
        _fail("source_repository_mismatch")

    legacy = _validate_registry_item(
        identity_reader(SOURCE_REPOSITORY, SOURCE_RUNNER_ID),
        repository=SOURCE_REPOSITORY,
        runner_id=SOURCE_RUNNER_ID,
        runner_name=SOURCE_RUNNER_NAME,
    )
    target = _validate_registry_item(
        identity_reader(TARGET_REPOSITORY, TARGET_RUNNER_ID),
        repository=TARGET_REPOSITORY,
        runner_id=TARGET_RUNNER_ID,
        runner_name=TARGET_RUNNER_NAME,
    )
    validated_home = validate_target_home(runner_home)
    snapshot = _normalize_snapshot(snapshot_reader(validated_home), validated_home)
    executable = validated_home / "bin" / LISTENER_NAME
    version = str(version_reader(executable) or "").strip()
    if not version_is_supported(version):
        _fail("listener_version_unsupported")
    return {
        "source_host": actual_host,
        "source_runner_name": actual_runner_name,
        "source_repository": actual_repository,
        "source_registry_status": legacy["status"],
        "source_registry_busy": legacy["busy"],
        "target_repository": TARGET_REPOSITORY,
        "target_runner_id": TARGET_RUNNER_ID,
        "target_runner_name": TARGET_RUNNER_NAME,
        "target_home": validated_home,
        "target_registry_status": target["status"],
        "target_registry_busy": target["busy"],
        "target_listener_version": version,
        "snapshot": snapshot,
        "identity_verified": True,
    }


def execute(
    *,
    mode: str,
    confirm: str,
    evidence_file: Path,
    host: str | None = None,
    platform: str | None = None,
    runner_name: str | None = None,
    repository: str | None = None,
    runner_home: Path | None = None,
    identity_reader: IdentityReader = default_identity_reader,
    snapshot_reader: SnapshotReader = _default_snapshot_reader,
    version_reader: VersionReader = _read_file_version,
    starter: Starter = _default_starter,
    stopper: Stopper = _default_stopper,
    wait_reader: WaitReader | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    wait_seconds: float = 30.0,
) -> dict[str, Any]:
    selected_home = runner_home or default_target_home()
    selected_host = host or socket.gethostname()
    selected_name = runner_name if runner_name is not None else os.environ.get("RUNNER_NAME", "")
    selected_repo = repository if repository is not None else os.environ.get("GITHUB_REPOSITORY", "")
    payload = _base_evidence(
        mode=mode,
        runner_home=selected_home,
        source_host=selected_host,
        source_runner_name=selected_name,
        repository=selected_repo,
    )
    try:
        if mode not in ALLOWED_MODES:
            _fail("mode_not_allowlisted")
        expected_confirm = READONLY_CONFIRM if mode == READONLY_MODE else RECOVERY_CONFIRM
        if confirm != expected_confirm:
            _fail("confirmation_invalid")
        context = _collect(
            runner_home=selected_home,
            host=host,
            platform=platform,
            runner_name=runner_name,
            repository=repository,
            identity_reader=identity_reader,
            snapshot_reader=snapshot_reader,
            version_reader=version_reader,
        )
        snapshot = context["snapshot"]
        payload.update(
            {
                "source_host": context["source_host"],
                "source_runner_name": context["source_runner_name"],
                "source_repository": context["source_repository"],
                "source_registry_status": context["source_registry_status"],
                "source_registry_busy": context["source_registry_busy"],
                "target_repository": context["target_repository"],
                "target_runner_id": context["target_runner_id"],
                "target_runner_name": context["target_runner_name"],
                "target_runner_home": str(context["target_home"]),
                "target_listener_executable": snapshot["expected_executable"],
                "target_listener_version": context["target_listener_version"],
                "target_listener_pids": snapshot["matching_pids"],
                "observed_listener_processes": snapshot["observed"],
                "target_registry_status": context["target_registry_status"],
                "target_registry_busy": context["target_registry_busy"],
                "identity_verified": True,
            }
        )
        if mode == READONLY_MODE:
            payload.update({"ok": True, "result": "DESKTOP_DEDICATED_LISTENER_READONLY_OK"})
            return _write(evidence_file, payload)

        if context["target_registry_busy"]:
            _fail("target_runner_active_work")
        matching = snapshot["matching_pids"]
        status = context["target_registry_status"]
        if status == "online":
            if len(matching) == 1:
                payload.update(
                    {"ok": True, "result": "DESKTOP_DEDICATED_LISTENER_ALREADY_HEALTHY"}
                )
                return _write(evidence_file, payload)
            _fail("target_registry_online_without_exact_listener")
        if status != "offline":
            _fail("target_registry_status_invalid")

        action = "restart" if matching else "start"
        payload["action"] = action
        payload["action_count"] = 1
        if matching:
            stopper(matching[0])
        starter(context["target_home"])
        if wait_reader is None:
            observed_after = _default_wait_reader(
                context["target_home"],
                snapshot_reader,
                timeout_seconds=wait_seconds,
                sleep_fn=sleep_fn,
            )
        else:
            observed_after = wait_reader(context["target_home"])
        after = _normalize_snapshot(observed_after, context["target_home"])
        if len(after["matching_pids"]) != 1:
            _fail("listener_post_action_identity_invalid")
        after_version = str(version_reader(context["target_home"] / "bin" / LISTENER_NAME) or "").strip()
        if not version_is_supported(after_version):
            _fail("listener_version_unsupported")
        target_after = _validate_registry_item(
            identity_reader(TARGET_REPOSITORY, TARGET_RUNNER_ID),
            repository=TARGET_REPOSITORY,
            runner_id=TARGET_RUNNER_ID,
            runner_name=TARGET_RUNNER_NAME,
        )
        if target_after["status"] != "online" or target_after["busy"]:
            _fail("target_runner_not_online_after_action")
        payload.update(
            {
                "ok": True,
                "result": (
                    "DESKTOP_DEDICATED_LISTENER_RESTARTED"
                    if action == "restart"
                    else "DESKTOP_DEDICATED_LISTENER_STARTED"
                ),
                "target_listener_version": after_version,
                "target_listener_pids": after["matching_pids"],
                "observed_listener_processes": after["observed"],
                "target_registry_status": target_after["status"],
                "target_registry_busy": target_after["busy"],
            }
        )
    except DedicatedListenerError as exc:
        payload["block_reason"] = exc.code
    except (OSError, TypeError, ValueError):
        payload["block_reason"] = "dedicated_listener_probe_failed"
    return _write(evidence_file, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=ALLOWED_MODES, required=True)
    parser.add_argument("--confirm", required=True)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=Path("artifacts/desktop-dedicated-listener/evidence.json"),
    )
    args = parser.parse_args()
    result = execute(mode=args.mode, confirm=args.confirm, evidence_file=args.evidence_file.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
