from copy import deepcopy

from scripts.validate_credential_control_plane import validate


def base_environments():
    return {
        "canonical_environments": ["dev", "hml", "prod"],
        "environments": {
            "dev": {"api_app": "reqsys-api-dev", "required_secret_names": ["JWT_SECRET"]},
            "hml": {"api_app": "reqsys-api-stg", "required_secret_names": ["JWT_SECRET"]},
            "prod": {"api_app": "reqsys-api", "required_secret_names": ["JWT_SECRET"]},
        },
    }


def base_control_plane():
    return {
        "principles": {"stores_secret_values": False},
        "lifecycle": {"allowed_status": ["UNKNOWN", "ACTIVE"]},
        "providers": {"fly": {"type": "secret_store"}},
        "credentials": [
            {
                "credential_id": "jwt-dev",
                "provider": "fly",
                "secret_reference": "JWT_SECRET",
                "status": "UNKNOWN",
            },
            {
                "credential_id": "jwt-hml",
                "provider": "fly",
                "secret_reference": "JWT_SECRET",
                "status": "UNKNOWN",
            },
            {
                "credential_id": "jwt-prod",
                "provider": "fly",
                "secret_reference": "JWT_SECRET",
                "status": "UNKNOWN",
            },
        ],
        "bindings": [
            {"credential_id": "jwt-dev", "environment": "dev", "consumer": "reqsys-api-dev"},
            {"credential_id": "jwt-hml", "environment": "hml", "consumer": "reqsys-api-stg"},
            {"credential_id": "jwt-prod", "environment": "prod", "consumer": "reqsys-api"},
        ],
    }


def test_control_plane_valido():
    assert validate(base_control_plane(), base_environments()) == []


def test_rejeita_valor_secreto_versionado():
    control_plane = base_control_plane()
    control_plane["credentials"][0]["secret_value"] = "nao-deve-estar-aqui"
    errors = validate(control_plane, base_environments())
    assert any("campos de valor secreto proibidos" in error for error in errors)


def test_rejeita_binding_para_ambiente_nao_canonico():
    control_plane = base_control_plane()
    control_plane["bindings"][0]["environment"] = "staging"
    errors = validate(control_plane, base_environments())
    assert any("ambiente não canônico" in error for error in errors)


def test_detecta_material_requerido_sem_binding():
    control_plane = deepcopy(base_control_plane())
    control_plane["bindings"] = [
        binding for binding in control_plane["bindings"] if binding["environment"] != "prod"
    ]
    errors = validate(control_plane, base_environments())
    assert any("material requerido sem binding" in error for error in errors)
