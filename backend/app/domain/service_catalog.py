"""Catálogo mínimo do ReqSys Service Management (RSM-03).

Define o contrato declarativo de campos de uma `ServiceOffering` e a validação
fail-closed da entrada enviada na abertura de um `ServiceCase(type=REQUEST)`.

O módulo é puro: não depende de FastAPI, SQLAlchemy, GitHub ou Teams.
Persistência e exposição HTTP entram por adaptadores em `app/api/service_catalog.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from app.domain.service_management import ServiceManagementValidationError

CATALOG_SCHEMA_VERSION = '1.0.0'
FIELD_KEY_RE = re.compile(r'^[a-z][a-z0-9_]{0,59}$')
OFFERING_CODE_RE = re.compile(r'^[A-Z0-9][A-Z0-9_-]+$')
MAX_FIELDS_PER_OFFERING = 30
DEFAULT_STRING_MAX_LENGTH = 500
ABSOLUTE_STRING_MAX_LENGTH = 4000


class OfferingFieldType(str, Enum):
    STRING = 'STRING'
    INTEGER = 'INTEGER'
    BOOLEAN = 'BOOLEAN'
    ENUM = 'ENUM'


class OfferingInactiveError(ServiceManagementValidationError):
    """Oferta existente porém inativa não aceita abertura de solicitação."""


class OfferingSubmissionError(ServiceManagementValidationError):
    """Entrada enviada não satisfaz o esquema declarativo da oferta."""


def _field_key(value: Any) -> str:
    normalized = str(value or '').strip()
    if not FIELD_KEY_RE.fullmatch(normalized):
        raise ServiceManagementValidationError(
            f'key de campo inválida: {normalized!r} (esperado snake_case minúsculo)'
        )
    return normalized


def normalize_offering_code(value: Any) -> str:
    normalized = str(value or '').strip().upper()
    if not normalized:
        raise ServiceManagementValidationError('code da oferta deve ser informado')
    if len(normalized) > 80:
        raise ServiceManagementValidationError('code da oferta excede 80 caracteres')
    if not OFFERING_CODE_RE.fullmatch(normalized):
        raise ServiceManagementValidationError('code da oferta possui formato inválido')
    return normalized


@dataclass(frozen=True, slots=True)
class OfferingField:
    """Especificação declarativa de um campo de entrada da oferta."""

    key: str
    label: str
    field_type: OfferingFieldType
    required: bool = False
    options: tuple[str, ...] = ()
    max_length: int = DEFAULT_STRING_MAX_LENGTH
    min_value: int | None = None
    max_value: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'key', _field_key(self.key))
        label = str(self.label or '').strip()
        if not label:
            raise ServiceManagementValidationError(f'label do campo {self.key} deve ser informado')
        if len(label) > 200:
            raise ServiceManagementValidationError(f'label do campo {self.key} excede 200 caracteres')
        object.__setattr__(self, 'label', label)
        if not isinstance(self.field_type, OfferingFieldType):
            raise ServiceManagementValidationError(f'type do campo {self.key} inválido')
        if not isinstance(self.required, bool):
            raise ServiceManagementValidationError(f'required do campo {self.key} deve ser booleano')

        options = tuple(str(option).strip() for option in self.options)
        if self.field_type is OfferingFieldType.ENUM:
            if not options:
                raise ServiceManagementValidationError(f'campo ENUM {self.key} exige options')
            if any(not option for option in options):
                raise ServiceManagementValidationError(f'options do campo {self.key} não podem ser vazias')
            if len(set(options)) != len(options):
                raise ServiceManagementValidationError(f'options do campo {self.key} possuem duplicidade')
        elif options:
            raise ServiceManagementValidationError(f'options só se aplicam a campo ENUM ({self.key})')
        object.__setattr__(self, 'options', options)

        if self.field_type is OfferingFieldType.STRING:
            if not isinstance(self.max_length, int) or isinstance(self.max_length, bool):
                raise ServiceManagementValidationError(f'max_length do campo {self.key} deve ser inteiro')
            if not 1 <= self.max_length <= ABSOLUTE_STRING_MAX_LENGTH:
                raise ServiceManagementValidationError(
                    f'max_length do campo {self.key} deve estar entre 1 e {ABSOLUTE_STRING_MAX_LENGTH}'
                )

        for bound_name in ('min_value', 'max_value'):
            bound = getattr(self, bound_name)
            if bound is None:
                continue
            if self.field_type is not OfferingFieldType.INTEGER:
                raise ServiceManagementValidationError(
                    f'{bound_name} só se aplica a campo INTEGER ({self.key})'
                )
            if not isinstance(bound, int) or isinstance(bound, bool):
                raise ServiceManagementValidationError(f'{bound_name} do campo {self.key} deve ser inteiro')
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ServiceManagementValidationError(
                f'min_value do campo {self.key} não pode exceder max_value'
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'key': self.key,
            'label': self.label,
            'type': self.field_type.value,
            'required': self.required,
        }
        if self.field_type is OfferingFieldType.ENUM:
            payload['options'] = list(self.options)
        if self.field_type is OfferingFieldType.STRING:
            payload['max_length'] = self.max_length
        if self.min_value is not None:
            payload['min_value'] = self.min_value
        if self.max_value is not None:
            payload['max_value'] = self.max_value
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> 'OfferingField':
        if not isinstance(raw, Mapping):
            raise ServiceManagementValidationError('campo do esquema deve ser objeto')
        allowed = {'key', 'label', 'type', 'required', 'options', 'max_length', 'min_value', 'max_value'}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ServiceManagementValidationError(
                f'atributos não suportados no esquema de campo: {", ".join(unknown)}'
            )
        raw_type = str(raw.get('type') or '').strip().upper()
        try:
            field_type = OfferingFieldType(raw_type)
        except ValueError as exc:
            raise ServiceManagementValidationError(f'type de campo inválido: {raw_type!r}') from exc
        return cls(
            key=raw.get('key'),
            label=raw.get('label'),
            field_type=field_type,
            required=bool(raw.get('required', False)),
            options=tuple(raw.get('options') or ()),
            max_length=int(raw.get('max_length', DEFAULT_STRING_MAX_LENGTH)),
            min_value=raw.get('min_value'),
            max_value=raw.get('max_value'),
        )

    def validate_value(self, value: Any) -> Any:
        """Valida e normaliza um valor único, sem coerção implícita de tipo."""
        if self.field_type in (OfferingFieldType.STRING, OfferingFieldType.ENUM):
            if not isinstance(value, str):
                raise OfferingSubmissionError(f'campo {self.key} deve ser string')
            normalized = value.strip()
            if not normalized:
                raise OfferingSubmissionError(f'campo {self.key} não pode ser vazio')
            if self.field_type is OfferingFieldType.ENUM:
                if normalized not in self.options:
                    raise OfferingSubmissionError(
                        f'campo {self.key} deve ser um de: {", ".join(self.options)}'
                    )
                return normalized
            if len(normalized) > self.max_length:
                raise OfferingSubmissionError(
                    f'campo {self.key} excede {self.max_length} caracteres'
                )
            return normalized
        if self.field_type is OfferingFieldType.INTEGER:
            # bool é subclasse de int: recusar explicitamente para manter fail-closed.
            if isinstance(value, bool) or not isinstance(value, int):
                raise OfferingSubmissionError(f'campo {self.key} deve ser inteiro')
            if self.min_value is not None and value < self.min_value:
                raise OfferingSubmissionError(f'campo {self.key} deve ser >= {self.min_value}')
            if self.max_value is not None and value > self.max_value:
                raise OfferingSubmissionError(f'campo {self.key} deve ser <= {self.max_value}')
            return value
        if not isinstance(value, bool):
            raise OfferingSubmissionError(f'campo {self.key} deve ser booleano')
        return value


@dataclass(frozen=True, slots=True)
class OfferingFieldSchema:
    """Conjunto declarativo e ordenado de campos aceitos por uma oferta."""

    fields: tuple[OfferingField, ...] = ()
    schema_version: str = CATALOG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        fields = tuple(self.fields)
        if len(fields) > MAX_FIELDS_PER_OFFERING:
            raise ServiceManagementValidationError(
                f'esquema excede {MAX_FIELDS_PER_OFFERING} campos'
            )
        keys = [field.key for field in fields]
        if len(set(keys)) != len(keys):
            raise ServiceManagementValidationError('esquema possui keys duplicadas')
        object.__setattr__(self, 'fields', fields)
        if self.schema_version != CATALOG_SCHEMA_VERSION:
            raise ServiceManagementValidationError(
                f'schema_version do catálogo deve ser {CATALOG_SCHEMA_VERSION}'
            )

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(field.key for field in self.fields)

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'fields': [field.to_dict() for field in self.fields],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> 'OfferingFieldSchema':
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ServiceManagementValidationError('field_schema deve ser objeto')
        unknown = sorted(set(raw) - {'fields', 'schema_version'})
        if unknown:
            raise ServiceManagementValidationError(
                f'atributos não suportados em field_schema: {", ".join(unknown)}'
            )
        raw_fields = raw.get('fields') or ()
        if not isinstance(raw_fields, Sequence) or isinstance(raw_fields, (str, bytes)):
            raise ServiceManagementValidationError('field_schema.fields deve ser lista')
        return cls(
            fields=tuple(OfferingField.from_dict(item) for item in raw_fields),
            schema_version=str(raw.get('schema_version') or CATALOG_SCHEMA_VERSION),
        )

    def validate_submission(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        """Valida a entrada fail-closed e devolve apenas os campos declarados.

        Rejeita chave desconhecida, campo obrigatório ausente/nulo e tipo divergente.
        """
        data = dict(payload or {})
        if not isinstance(payload, (Mapping, type(None))):
            raise OfferingSubmissionError('fields deve ser objeto')
        unknown = sorted(set(data) - self.keys)
        if unknown:
            raise OfferingSubmissionError(
                f'campos não declarados na oferta: {", ".join(unknown)}'
            )
        normalized: dict[str, Any] = {}
        for field in self.fields:
            if field.key not in data or data[field.key] is None:
                if field.required:
                    raise OfferingSubmissionError(f'campo obrigatório ausente: {field.key}')
                continue
            normalized[field.key] = field.validate_value(data[field.key])
        return normalized
