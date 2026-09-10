from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict


PROFILE = "excel_sql_sharepoint_sync"
SUPPORTED_SOURCE = "excel"
SUPPORTED_DESTINATION = "sharepoint"
SUPPORTED_SQL_INPUT_MODE = "json"
SUPPORTED_OPERATION = "upsert"


class IntegrationProfileError(ValueError):
    """Raised when an integration profile is invalid or unsupported."""


@dataclass(frozen=True)
class GeneratedIntegrationArtifacts:
    profile: str
    office_script: str
    sql_procedure_template: str
    power_automate_contract: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile,
            "office_script": self.office_script,
            "sql_procedure_template": self.sql_procedure_template,
            "power_automate_contract": self.power_automate_contract,
        }


def validate_profile(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise IntegrationProfileError("O perfil deve ser um objeto JSON/YAML.")

    if payload.get("profile") != PROFILE:
        raise IntegrationProfileError(f"Perfil não suportado: {payload.get('profile')!r}")

    source = payload.get("source") or {}
    sql = payload.get("sql") or {}
    destination = payload.get("destination") or {}
    governance = payload.get("governance") or {}

    if source.get("type") != SUPPORTED_SOURCE:
        raise IntegrationProfileError("source.type deve ser 'excel'.")
    if not source.get("table"):
        raise IntegrationProfileError("source.table é obrigatório.")
    if not source.get("identifier_column"):
        raise IntegrationProfileError("source.identifier_column é obrigatório.")

    pattern = source.get("identifier_pattern", r"^\d+$")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise IntegrationProfileError("source.identifier_pattern é inválido.") from exc

    if sql.get("input_mode") != SUPPORTED_SQL_INPUT_MODE:
        raise IntegrationProfileError("sql.input_mode deve ser 'json'.")
    if not sql.get("procedure"):
        raise IntegrationProfileError("sql.procedure é obrigatório.")
    if not sql.get("key_field"):
        raise IntegrationProfileError("sql.key_field é obrigatório.")

    if destination.get("type") != SUPPORTED_DESTINATION:
        raise IntegrationProfileError("destination.type deve ser 'sharepoint'.")
    if destination.get("operation") != SUPPORTED_OPERATION:
        raise IntegrationProfileError("destination.operation deve ser 'upsert'.")
    if not destination.get("list"):
        raise IntegrationProfileError("destination.list é obrigatório.")
    if not destination.get("business_key"):
        raise IntegrationProfileError("destination.business_key é obrigatório.")

    required_governance = {
        "deduplicate": True,
        "correlation_id": True,
        "idempotent": True,
        "quarantine_invalid_rows": True,
    }
    for key, expected in required_governance.items():
        if governance.get(key) is not expected:
            raise IntegrationProfileError(f"governance.{key} deve ser true.")


def generate_artifacts(payload: Dict[str, Any]) -> GeneratedIntegrationArtifacts:
    validate_profile(payload)

    source = payload["source"]
    sql = payload["sql"]
    destination = payload["destination"]

    office_script = _build_office_script(
        table_name=source["table"],
        identifier_column=source["identifier_column"],
        identifier_pattern=source.get("identifier_pattern", r"^\d+$"),
    )
    sql_template = _build_sql_template(
        procedure=sql["procedure"],
        key_field=sql["key_field"],
    )
    power_automate_contract = {
        "profile": PROFILE,
        "steps": [
            "generate_correlation_id",
            "run_excel_identifier_extractor",
            "reject_or_quarantine_invalid_rows",
            "execute_sql_procedure_v2",
            "parse_sql_result",
            "sharepoint_lookup_by_business_key",
            "sharepoint_create_or_update",
            "verify_sharepoint_persistence",
        ],
        "sql": {
            "procedure": sql["procedure"],
            "input_parameter": "IdsJson",
            "correlation_parameter": "CorrelationId",
        },
        "sharepoint": {
            "list": destination["list"],
            "business_key": destination["business_key"],
            "operation": "upsert",
        },
        "controls": {
            "deduplicate": True,
            "idempotent": True,
            "correlation_id": True,
            "independent_final_read": True,
        },
    }

    return GeneratedIntegrationArtifacts(
        profile=PROFILE,
        office_script=office_script,
        sql_procedure_template=sql_template,
        power_automate_contract=power_automate_contract,
    )


def generate_artifacts_json(payload: Dict[str, Any]) -> str:
    return json.dumps(generate_artifacts(payload).as_dict(), ensure_ascii=False, indent=2)


def _build_office_script(table_name: str, identifier_column: str, identifier_pattern: str) -> str:
    escaped_pattern = identifier_pattern.replace("\\", "\\\\").replace("`", "\\`")
    return f'''interface ExtractionResult {{
  identifiers: string[];
  invalid: {{ row: number; value: string; reason: string }}[];
  totalRows: number;
  validCount: number;
  invalidCount: number;
}}

function main(workbook: ExcelScript.Workbook): string {{
  const table = workbook.getTables().find(t => t.getName() === "{table_name}");
  if (!table) throw new Error("Tabela '{table_name}' não encontrada.");

  const column = table.getColumns().find(c => c.getName() === "{identifier_column}");
  if (!column) throw new Error("Coluna '{identifier_column}' não encontrada.");

  const values = column.getRangeBetweenHeaderAndTotal().getTexts();
  const pattern = new RegExp(`{escaped_pattern}`);
  const identifiers = new Set<string>();
  const invalid: ExtractionResult["invalid"] = [];

  values.forEach((row, index) => {{
    const value = (row[0] ?? "").trim();
    if (!value) return;
    if (!pattern.test(value)) {{
      invalid.push({{ row: index + 2, value, reason: "Identificador fora do padrão." }});
      return;
    }}
    identifiers.add(value);
  }});

  const result: ExtractionResult = {{
    identifiers: Array.from(identifiers),
    invalid,
    totalRows: values.length,
    validCount: identifiers.size,
    invalidCount: invalid.length
  }};
  return JSON.stringify(result);
}}
'''


def _build_sql_template(procedure: str, key_field: str) -> str:
    return f'''CREATE OR ALTER PROCEDURE {procedure}
    @IdsJson NVARCHAR(MAX),
    @CorrelationId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF ISJSON(@IdsJson) <> 1
        THROW 51001, 'IdsJson inválido.', 1;

    IF EXISTS (
        SELECT 1
        FROM OPENJSON(@IdsJson)
        WHERE [type] <> 1
           OR LTRIM(RTRIM([value])) = ''
           OR LTRIM(RTRIM([value])) LIKE '%[^0-9]%'
    )
        THROW 51002, 'Lista contém identificador inválido.', 1;

    ;WITH Identificadores AS (
        SELECT DISTINCT LTRIM(RTRIM([value])) AS Identificador
        FROM OPENJSON(@IdsJson)
    )
    SELECT
        resultado.*,
        @CorrelationId AS CorrelationId
    FROM (
        -- Substituir apenas este bloco pela consulta complexa de negócio.
        -- Ela deve retornar o campo '{key_field}'.
        SELECT CAST(NULL AS VARCHAR(100)) AS {key_field}
        WHERE 1 = 0
    ) resultado
    INNER JOIN Identificadores ids
        ON ids.Identificador = CONVERT(VARCHAR(100), resultado.{key_field});
END;
'''
