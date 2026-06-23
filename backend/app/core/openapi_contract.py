"""OpenAPI contract post-processing for security tooling compatibility."""

from __future__ import annotations

import os
from collections.abc import Iterable, MutableMapping
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.routers.auth_boundary import PUBLIC_AUTH_WHITELIST

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
BEARER_SECURITY = [{"BearerAuth": []}]
PUBLIC_WITHOUT_TOKEN = PUBLIC_AUTH_WHITELIST - {"/api/auth/refresh"}
COMPOSITION_KEYS = ("anyOf", "oneOf", "allOf")
INTEGER_BOUND_KEYS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
)
GENERIC_TEXT_PARAMETER_PATTERN = r"^[^\x00-\x1F\x7F]{0,512}$"
GENERIC_PATH_PARAMETER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"
PATH_LIKE_PARAMETER_PATTERN = r"^[^\x00-\x1F\x7F]{0,2048}$"
SENSITIVE_PARAMETER_PATTERN = r"^[^\x00-\x1F\x7F]{0,4096}$"
DEFAULT_TEXT_PARAMETER_MAX_LENGTH = 512
TEXT_PARAMETER_MAX_LENGTHS = {
    "api_key": 4096,
    "authorization": 8192,
    "base_url": 4096,
    "last-event-id": 1024,
    "last_event_id": 1024,
    "path": 2048,
    "query": 2048,
    "url": 4096,
    "x-provider-api-key": 4096,
}
TEXT_PARAMETER_PATTERNS = {
    "api_key": SENSITIVE_PARAMETER_PATTERN,
    "authorization": SENSITIVE_PARAMETER_PATTERN,
    "base_url": PATH_LIKE_PARAMETER_PATTERN,
    "path": PATH_LIKE_PARAMETER_PATTERN,
    "query": PATH_LIKE_PARAMETER_PATTERN,
    "url": PATH_LIKE_PARAMETER_PATTERN,
    "x-provider-api-key": SENSITIVE_PARAMETER_PATTERN,
}
INTEGER_PARAMETER_BOUNDS = {
    "artifactversion": (1, 2_147_483_647),
    "item_index": (0, 10_000),
    "limit": (1, 1_000),
    "offset": (0, 1_000_000),
    "sample_rows": (1, 1_000),
    "tail": (1, 10_000),
}
DEFAULT_INTEGER_PARAMETER_BOUNDS = (0, 2_147_483_647)
BODY_METHODS = {"post", "put", "patch"}
NOT_ACCEPTABLE_METHODS = {"get", "post", "put", "patch", "delete"}
NOT_FOUND_METHODS = {"get", "put", "head", "delete"}
PROTECTED_RESPONSE_REFS = {
    "401": "#/components/responses/UnauthorizedError",
    "403": "#/components/responses/ForbiddenError",
}
STANDARD_RESPONSE_REFS = {
    "406": "#/components/responses/NotAcceptableError",
    "415": "#/components/responses/UnsupportedMediaTypeError",
    "429": "#/components/responses/RateLimitError",
    "default": "#/components/responses/DefaultError",
}


def install_openapi_contract(app: FastAPI) -> None:
    """Install the OpenAPI builder used by docs and security tooling."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        apply_openapi_contract(schema)
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi


def apply_openapi_contract(schema: dict[str, Any]) -> None:
    _apply_servers(schema)
    _apply_auth_contract(schema)
    _apply_response_contract(schema)
    _ensure_unique_operation_ids(schema)
    _normalize_composed_schema_defaults(schema)
    _apply_parameter_schema_contract(schema)
    _normalize_integer_schema_bounds(schema)


def _apply_servers(schema: dict[str, Any]) -> None:
    raw_url = (
        os.getenv("OPENAPI_SERVER_URL", "").strip()
        or os.getenv("PUBLIC_BASE_URL", "").strip()
        or "/"
    )
    schema["servers"] = [{"url": normalize_openapi_server_url(raw_url)}]


def normalize_openapi_server_url(raw_url: str | None) -> str:
    raw = str(raw_url or "").strip()
    if not raw or raw == "/":
        return "/"

    parsed = urlparse(raw)
    if parsed.scheme == "https" and parsed.netloc:
        return raw.rstrip("/")

    return "/"


def _apply_auth_contract(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes.update(
        {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT access or refresh token in Authorization header.",
            },
        }
    )
    schema["security"] = BEARER_SECURITY

    for path, _method, operation in _iter_operations(schema):
        if path in PUBLIC_WITHOUT_TOKEN:
            operation["security"] = []
        else:
            operation["security"] = BEARER_SECURITY


def _apply_response_contract(schema: dict[str, Any]) -> None:
    _ensure_error_components(schema)

    for path, method, operation in _iter_operations(schema):
        responses = operation.setdefault("responses", {})
        _set_response_ref(responses, "429", STANDARD_RESPONSE_REFS["429"])
        _set_response_ref(responses, "default", STANDARD_RESPONSE_REFS["default"])

        if method in NOT_ACCEPTABLE_METHODS:
            _set_response_ref(responses, "406", STANDARD_RESPONSE_REFS["406"])
        if method in NOT_FOUND_METHODS:
            _set_response_ref(responses, "404", "#/components/responses/NotFoundError")
        if method in BODY_METHODS and "requestBody" in operation:
            _set_response_ref(responses, "415", STANDARD_RESPONSE_REFS["415"])
        if path not in PUBLIC_WITHOUT_TOKEN:
            for status, ref in PROTECTED_RESPONSE_REFS.items():
                _set_response_ref(responses, status, ref)


def _ensure_error_components(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.setdefault(
        "ErrorResponse",
        {
            "type": "object",
            "title": "ErrorResponse",
            "additionalProperties": False,
            "properties": {
                "detail": {
                    "type": "string",
                    "title": "Detail",
                    "maxLength": 4096,
                    "description": "Human-readable error detail.",
                },
            },
            "required": ["detail"],
        },
    )

    responses = components.setdefault("responses", {})
    response_specs = {
        "UnauthorizedError": "Authentication credentials are missing or invalid.",
        "ForbiddenError": "The authenticated principal is not allowed to access this resource.",
        "NotFoundError": "The requested resource was not found.",
        "NotAcceptableError": "The requested response representation is not acceptable.",
        "UnsupportedMediaTypeError": "The request media type is not supported.",
        "RateLimitError": "The request was rate limited.",
        "DefaultError": "Unexpected error response.",
    }
    for name, description in response_specs.items():
        responses.setdefault(name, _error_response(description))


def _error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
            },
        },
    }


def _set_response_ref(
    responses: MutableMapping[str, Any],
    status: str,
    ref: str,
) -> None:
    responses.setdefault(status, {"$ref": ref})


def _ensure_unique_operation_ids(schema: dict[str, Any]) -> None:
    seen: set[str] = set()
    for path, method, operation in _iter_operations(schema):
        base_id = str(operation.get("operationId") or _fallback_operation_id(method, path))
        operation_id = base_id
        if operation_id in seen:
            operation_id = f"{base_id}_{method}"
            suffix = 2
            while operation_id in seen:
                operation_id = f"{base_id}_{method}_{suffix}"
                suffix += 1
            operation["operationId"] = operation_id
        seen.add(operation_id)


def _apply_parameter_schema_contract(schema: dict[str, Any]) -> None:
    """Add conservative bounds to OpenAPI operation parameters.

    FastAPI often emits unbounded path/query/header parameter schemas even when
    runtime code treats them as identifiers, cursors, or small control strings.
    Bound only operation parameters here; request/response body models keep
    their explicit Pydantic contracts so this post-processor does not invent
    body semantics.
    """

    for _path, _method, operation in _iter_operations(schema):
        parameters = operation.get("parameters")
        if not isinstance(parameters, list):
            continue
        for parameter in parameters:
            if not isinstance(parameter, MutableMapping):
                continue
            parameter_schema = parameter.get("schema")
            if not isinstance(parameter_schema, MutableMapping):
                continue

            name = str(parameter.get("name") or "").strip()
            location = str(parameter.get("in") or "").strip().lower()
            if _schema_has_string_type(parameter_schema):
                _apply_string_parameter_contract(
                    parameter_schema,
                    name=name,
                    location=location,
                    required=bool(parameter.get("required")),
                )
            if _schema_has_integer_type(parameter_schema):
                _apply_integer_parameter_contract(parameter_schema, name=name)


def _apply_string_parameter_contract(
    parameter_schema: MutableMapping[str, Any],
    *,
    name: str,
    location: str,
    required: bool,
) -> None:
    normalized_name = name.strip().lower()
    max_length = TEXT_PARAMETER_MAX_LENGTHS.get(
        normalized_name,
        DEFAULT_TEXT_PARAMETER_MAX_LENGTH,
    )
    if location == "path" and normalized_name != "path":
        max_length = min(max_length, 256)

    parameter_schema.setdefault("maxLength", max_length)
    if required and location == "path":
        parameter_schema.setdefault("minLength", 1)

    if "pattern" in parameter_schema:
        return

    if location == "path" and normalized_name != "path":
        parameter_schema["pattern"] = GENERIC_PATH_PARAMETER_PATTERN
        return

    parameter_schema["pattern"] = TEXT_PARAMETER_PATTERNS.get(
        normalized_name,
        GENERIC_TEXT_PARAMETER_PATTERN,
    )


def _apply_integer_parameter_contract(
    parameter_schema: MutableMapping[str, Any],
    *,
    name: str,
) -> None:
    minimum, maximum = INTEGER_PARAMETER_BOUNDS.get(
        name.strip().lower(),
        DEFAULT_INTEGER_PARAMETER_BOUNDS,
    )
    parameter_schema.setdefault("minimum", minimum)
    parameter_schema.setdefault("maximum", maximum)
    parameter_schema.setdefault("format", "int32")


def _normalize_composed_schema_defaults(node: Any) -> None:
    if isinstance(node, MutableMapping):
        _collapse_simple_anyof_types(node)
        if "default" in node and any(key in node for key in COMPOSITION_KEYS):
            node.pop("default", None)
        for value in list(node.values()):
            _normalize_composed_schema_defaults(value)
    elif isinstance(node, list):
        for value in node:
            _normalize_composed_schema_defaults(value)


def _normalize_integer_schema_bounds(node: Any) -> None:
    if isinstance(node, MutableMapping):
        if _schema_has_integer_type(node):
            for key in INTEGER_BOUND_KEYS:
                value = node.get(key)
                if isinstance(value, float) and value.is_integer():
                    # Pydantic can emit 100.0 for integer bounds; 42Crunch scan
                    # config generation expects integral JSON numbers here.
                    node[key] = int(value)
        for value in list(node.values()):
            _normalize_integer_schema_bounds(value)
    elif isinstance(node, list):
        for value in node:
            _normalize_integer_schema_bounds(value)


def _schema_has_integer_type(schema: MutableMapping[str, Any]) -> bool:
    schema_type = schema.get("type")
    return schema_type == "integer" or (isinstance(schema_type, list) and "integer" in schema_type)


def _schema_has_string_type(schema: MutableMapping[str, Any]) -> bool:
    schema_type = schema.get("type")
    return schema_type == "string" or (isinstance(schema_type, list) and "string" in schema_type)


def _collapse_simple_anyof_types(schema: MutableMapping[str, Any]) -> None:
    branches = schema.get("anyOf")
    if not isinstance(branches, list):
        return

    type_values: list[str] = []
    for branch in branches:
        if not isinstance(branch, dict) or set(branch) != {"type"}:
            return
        branch_type = branch.get("type")
        if not isinstance(branch_type, str):
            return
        if branch_type not in type_values:
            type_values.append(branch_type)

    if not type_values:
        return

    schema.pop("anyOf", None)
    schema["type"] = type_values[0] if len(type_values) == 1 else type_values


def _iter_operations(schema: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method in HTTP_METHODS and isinstance(operation, dict):
                yield path, method, operation


def _fallback_operation_id(method: str, path: str) -> str:
    normalized_path = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    return f"{method}_{normalized_path or 'root'}"
