#!/usr/bin/env python3
"""Native, bounded contract projection for ReqSys base + production YAML.

Not a Docker Compose implementation or a captured Compose rendering. Only the
fields used by this repository's production contract are interpreted. No host
environment, .env, subprocess, daemon, runtime or secret source is consulted.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Mapping

import yaml

SERVICES = frozenset({"api", "db", "mailhog", "frontend", "kb", "nginx"})
FIELDS = frozenset({"restart", "environment", "depends_on", "profiles", "ports",
                    "healthcheck", "build"})
OPAQUE_FIELDS = frozenset({"logging", "volumes", "networks", "image", "expose", "command"})
REQUIRED = frozenset({"JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE", "AZURE_TENANT_ID",
                      "AZURE_CLIENT_ID", "CORS_ORIGINS", "POSTGRES_PASSWORD"})
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
DURATION = re.compile(r"[1-9][0-9]*(?:ms|s|m|h)")


class ContractError(ValueError):
    """Diagnostic codes and field names only; never interpolate input values."""


class OverrideMap(dict):
    """Only services.<name>.depends_on: !override is supported."""


class ContractLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result or key == "<<":
                raise ContractError("unsupported_or_duplicate_mapping_key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _override(loader, node):
    if not isinstance(node, yaml.MappingNode):
        raise ContractError("override_requires_mapping")
    return OverrideMap(loader.construct_mapping(node, deep=True))


ContractLoader.add_constructor("!override", _override)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ContractError(code)


def interpolate(value: str, environment: Mapping[str, str], depth: int = 0) -> str:
    _require(depth < 20, "interpolation_depth_exceeded")
    out = []
    i = 0
    while i < len(value):
        if value[i] != "$":
            out.append(value[i])
            i += 1
        elif value.startswith("$$", i):
            out.append("$")
            i += 2
        elif value.startswith("${", i):
            level, end = 1, i + 2
            while end < len(value) and level:
                if value.startswith("${", end):
                    level += 1
                    end += 2
                elif value[end] == "}":
                    level -= 1
                    end += 1
                else:
                    end += 1
            _require(level == 0, "unclosed_interpolation")
            expression = value[i + 2:end - 1]
            name = NAME.match(expression)
            _require(name is not None, "unsupported_interpolation")
            key = name.group()
            rest = expression[len(key):]
            present = key in environment
            actual = environment.get(key, "")
            if not rest:
                replacement = actual
            else:
                operator = next((op for op in (":-", ":?", "-", "?") if rest.startswith(op)), None)
                _require(operator is not None, "unsupported_interpolation_operator")
                argument = rest[len(operator):]
                usable = present and (bool(actual) if operator.startswith(":") else True)
                if operator.endswith("?"):
                    _require(usable, "required_variable:" + key)
                    replacement = actual
                else:
                    replacement = actual if usable else interpolate(argument, environment, depth + 1)
            out.append(replacement)
            i = end
        else:
            name = NAME.match(value, i + 1)
            if name:
                out.append(environment.get(name.group(), ""))
                i = name.end()
            else:
                out.append("$")
                i += 1
    return "".join(out)


def _walk(value, environment, path=(), depth=0):
    _require(depth < 30, "yaml_depth_exceeded")
    if isinstance(value, OverrideMap):
        _require(len(path) == 3 and path[0] == "services" and path[2] == "depends_on",
                 "override_outside_depends_on")
    if isinstance(value, dict):
        result = OverrideMap() if isinstance(value, OverrideMap) else {}
        for key, item in value.items():
            _require(isinstance(key, str), "mapping_key_must_be_string")
            result[key] = _walk(item, environment, path + (key,), depth + 1)
        return result
    if isinstance(value, list):
        return [_walk(item, environment, path, depth + 1) for item in value]
    if isinstance(value, str):
        return interpolate(value, environment)
    _require(value is None or type(value) in (bool, int, float), "unsupported_yaml_value")
    return value


def _mapping(value, code):
    _require(isinstance(value, dict), code)
    return value


def _strings(value, code):
    _require(isinstance(value, list) and all(isinstance(item, str) for item in value), code)
    _require(len(set(value)) == len(value), code + ":duplicate")
    return value


def _environment(value):
    if isinstance(value, list):
        result = {}
        for entry in _strings(value, "environment_list_invalid"):
            key, separator, item = entry.partition("=")
            _require(bool(separator) and NAME.fullmatch(key) is not None and key not in result,
                     "environment_entry_requires_explicit_value")
            result[key] = item
        return result
    value = _mapping(value, "environment_mapping_required")
    _require(all(NAME.fullmatch(key) and isinstance(item, str) for key, item in value.items()),
             "environment_value_must_be_explicit_string")
    return dict(value)


def _dependencies(value):
    if isinstance(value, list):
        value = {name: {"condition": "service_started"}
                 for name in _strings(value, "depends_on_list_invalid")}
    value = _mapping(value, "depends_on_mapping_required")
    result = OverrideMap() if isinstance(value, OverrideMap) else {}
    for name, options in value.items():
        _require(name in SERVICES, "dependency_not_in_contract")
        options = _mapping(options, "dependency_options_required")
        _require(set(options) == {"condition"} and options["condition"] in
                 ("service_started", "service_healthy"), "unsupported_dependency_options")
        result[name] = dict(options)
    return result


def _ports(value):
    result = []
    for item in _strings(value, "ports_short_syntax_required"):
        match = re.fullmatch(r"([0-9]+):([0-9]+)(?:/(tcp|udp))?", item)
        _require(match is not None, "unsupported_port_syntax")
        published, target, protocol = match.groups()
        _require(0 < int(published) <= 65535 and 0 < int(target) <= 65535, "invalid_port_range")
        result.append({"published": str(int(published)), "target": int(target),
                       "protocol": protocol or "tcp"})
    return result


def _health(value):
    value = _mapping(value, "healthcheck_mapping_required")
    _require(set(value) <= {"test", "interval", "timeout", "retries", "start_period"},
             "unsupported_healthcheck_field")
    if "test" in value:
        command = _strings(value["test"], "healthcheck_test_list_required")
        _require(len(command) >= 2 and command[0] in ("CMD", "CMD-SHELL"), "unsupported_healthcheck_test")
    for field in ("interval", "timeout", "start_period"):
        if field in value:
            _require(isinstance(value[field], str) and DURATION.fullmatch(value[field]) is not None,
                     "unsupported_healthcheck_duration")
    if "retries" in value:
        _require(type(value["retries"]) is int and value["retries"] > 0, "invalid_healthcheck_retries")
    return deepcopy(value)


def _build(value):
    if isinstance(value, str):
        return {"context": value}
    value = _mapping(value, "build_mapping_required")
    _require(set(value) <= {"context", "dockerfile", "args"}, "unsupported_build_field")
    for key in ("context", "dockerfile"):
        if key in value:
            _require(isinstance(value[key], str), "build_path_must_be_string")
    result = dict(value)
    if "args" in result:
        result["args"] = _environment(result["args"])
    return result


def _load(source: str, environment: Mapping[str, str]):
    _require(isinstance(source, str) and len(source) < 200000, "source_size_or_type_invalid")
    try:
        document = yaml.load(source, Loader=ContractLoader)
    except yaml.YAMLError:
        raise ContractError("unsupported_or_invalid_yaml") from None
    document = _mapping(document, "document_mapping_required")
    _require(set(document) <= {"services", "networks", "volumes", "x-logging"}, "unsupported_top_level_field")
    # Interpolation is applied independently to EACH file BEFORE any merge.
    document = _walk(document, environment)
    services = _mapping(document.get("services"), "services_mapping_required")
    _require(set(services) <= SERVICES, "service_not_in_contract")
    result = {}
    for name, service in services.items():
        service = _mapping(service, "service_mapping_required")
        _require(set(service) <= FIELDS | OPAQUE_FIELDS, "unsupported_service_field")
        projected = {}
        for key, value in service.items():
            if key in OPAQUE_FIELDS:
                continue  # These fields are explicitly outside this contract.
            if key == "environment":
                value = _environment(value)
            elif key == "depends_on":
                value = _dependencies(value)
            elif key == "ports":
                value = _ports(value)
            elif key == "healthcheck":
                value = _health(value)
            elif key == "build":
                value = _build(value)
            elif key == "profiles":
                value = _strings(value, "profiles_list_required")
                _require(bool(value), "empty_profiles_not_supported")
            elif key == "restart":
                _require(isinstance(value, str), "restart_string_required")
            projected[key] = value
        result[name] = projected
    return result


def evaluate_contract(base_source: str, production_source: str,
                      environment: Mapping[str, str], *, profiles: tuple[str, ...] = ()) -> dict:
    _require(isinstance(environment, Mapping) and
             all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()),
             "explicit_string_environment_required")
    _require(isinstance(profiles, tuple) and all(isinstance(item, str) for item in profiles),
             "explicit_profiles_tuple_required")
    base = _load(base_source, environment)
    overlay = _load(production_source, environment)
    _require(set(base) == SERVICES and set(overlay) == SERVICES, "exact_service_set_required")
    merged = deepcopy(base)
    for name, service in overlay.items():
        target = merged[name]
        for key, value in service.items():
            if key in ("environment", "depends_on", "healthcheck", "build"):
                if isinstance(value, OverrideMap):
                    target[key] = dict(value)
                else:
                    prior = target.get(key, {})
                    target[key] = {**prior, **value}
                    if key == "build" and "args" in prior and "args" in value:
                        target[key]["args"] = {**prior["args"], **value["args"]}
            elif key in ("ports", "profiles"):
                target[key] = target.get(key, []) + [item for item in value if item not in target.get(key, [])]
            else:
                target[key] = value
    active = sorted(name for name, service in merged.items()
                    if not service.get("profiles") or set(service["profiles"]) & set(profiles))
    for name in active:
        for dependency, options in merged[name].get("depends_on", {}).items():
            _require(dependency in active, "active_dependency_has_disabled_profile")
            if options["condition"] == "service_healthy":
                _require(bool(merged[dependency].get("healthcheck", {}).get("test")),
                         "healthy_dependency_without_healthcheck")
    return {"scope": "reqsys-production-contract-v1", "base_services": base,
            "services": merged, "active_services": active}


def validate_production_contract(model: dict, environment: Mapping[str, str]) -> None:
    services = model["services"]
    base = model["base_services"]
    active = set(model["active_services"])
    _require(all(service.get("restart") == "no" for service in base.values()), "base_restart_not_fail_fast")
    _require(active == SERVICES - {"mailhog"}, "production_service_set_invalid")
    _require(all(services[name].get("restart") == "on-failure:5" for name in active),
             "production_restart_not_bounded")
    _require(services["mailhog"].get("profiles") == ["local-mail"] and
             services["mailhog"].get("restart") == "no", "mailhog_must_be_opt_in")
    api = services["api"]
    env = api.get("environment", {})
    _require(env.get("APP_ENV") == "production" and env.get("PUBLIC_ENVIRONMENT") == "production"
             and env.get("ALLOW_DEMO_LOGIN") == "false", "production_identity_or_demo_invalid")
    for name in REQUIRED:
        _require(bool(environment.get(name)), "required_variable:" + name)
        actual = services["db"].get("environment", {}).get(name) if name == "POSTGRES_PASSWORD" else env.get(name)
        _require(actual == environment[name], "production_environment_mismatch:" + name)
    _require(env.get("MOVIMENTO_EMAIL_SMTP_HOST") == environment.get("MOVIMENTO_EMAIL_SMTP_HOST", ""),
             "production_mail_relay_inheritance")
    _require(api.get("depends_on") == {"db": {"condition": "service_healthy"}},
             "production_api_dependencies_invalid")
    _require(not services["db"].get("ports") and not api.get("ports"), "private_service_published")
    frontend = services["frontend"]
    _require(frontend.get("build", {}).get("dockerfile") == "Dockerfile.prod" and
             frontend.get("build", {}).get("args", {}).get("VITE_API_URL") == "/api", "frontend_production_build_invalid")
    _require("http://127.0.0.1/healthz" in frontend.get("healthcheck", {}).get("test", []),
             "frontend_healthcheck_invalid")
    gateway = services["nginx"]
    expected_port = str(int(environment.get("GATEWAY_PORT") or "8081"))
    _require(gateway.get("ports") == [{"target": 80, "published": expected_port, "protocol": "tcp"}],
             "gateway_publication_invalid")
    _require(gateway.get("depends_on", {}).get("frontend") == {"condition": "service_healthy"},
             "gateway_frontend_dependency_invalid")
    health = " ".join(gateway.get("healthcheck", {}).get("test", []))
    _require("http://127.0.0.1/" in health and "http://127.0.0.1/api/health" in health,
             "gateway_healthcheck_invalid")
