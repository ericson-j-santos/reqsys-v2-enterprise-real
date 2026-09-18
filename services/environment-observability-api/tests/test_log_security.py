import json
import logging

from app.main import JsonFormatter, LOG_SCHEMA_VERSION, parse_traceparent, redact


def test_parse_valid_w3c_traceparent():
    trace_id, span_id = parse_traceparent(
        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    )
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span_id == "00f067aa0ba902b7"


def test_rejects_invalid_or_zero_traceparent():
    assert parse_traceparent("invalid") == (None, None)
    assert parse_traceparent("00-00000000000000000000000000000000-00f067aa0ba902b7-01") == (None, None)
    assert parse_traceparent("00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01") == (None, None)


def test_redacts_nested_sensitive_keys_and_personal_data():
    payload = {
        "authorization": "Bearer abc.def.ghi",
        "nested": {
            "api_key": "secret-value",
            "message": "Contato user@example.com CPF 010.596.569-30 telefone 11 98919-6498",
        },
    }
    sanitized = redact(payload)
    rendered = json.dumps(sanitized)
    assert "abc.def.ghi" not in rendered
    assert "secret-value" not in rendered
    assert "user@example.com" not in rendered
    assert "010.596.569-30" not in rendered
    assert "98919-6498" not in rendered
    assert "[REDACTED]" in rendered


def test_json_formatter_never_emits_sensitive_values():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization Bearer token-value user@example.com 01059656930 11989196498",
        args=(),
        exc_info=None,
    )
    record.event_name = "security.redaction.test"
    record.event_category = "security"
    output = JsonFormatter().format(record)
    payload = json.loads(output)

    assert payload["log_schema_version"] == LOG_SCHEMA_VERSION
    assert payload["event_category"] == "security"
    for sensitive in ("token-value", "user@example.com", "01059656930", "11989196498"):
        assert sensitive not in output
    assert "deployment_id" in payload
    assert "region" in payload
    assert "instance_id" in payload
