from __future__ import annotations

import warnings
import json

import pytest

from app.main import app
from app.routers.auth_boundary import PUBLIC_AUTH_WHITELIST
from scripts.export_openapi import export_openapi

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
BEARER_SECURITY = [{"BearerAuth": []}]
PUBLIC_WITHOUT_TOKEN = PUBLIC_AUTH_WHITELIST - {"/api/auth/refresh"}
BODY_METHODS = {"post", "put", "patch"}
NOT_ACCEPTABLE_METHODS = {"get", "post", "put", "patch", "delete"}
NOT_FOUND_METHODS = {"get", "put", "head", "delete"}


def _schema() -> dict:
    app.openapi_schema = None
    return app.openapi()


def _operations(schema: dict):
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def test_openapi_declares_runtime_auth_schemes():
    schemes = _schema()["components"]["securitySchemes"]

    assert schemes["BearerAuth"]["type"] == "http"
    assert schemes["BearerAuth"]["scheme"] == "bearer"
    assert set(schemes) == {"BearerAuth"}


def test_openapi_marks_public_and_protected_operations_explicitly():
    operations = list(_operations(_schema()))
    assert operations

    for path, _method, operation in operations:
        if path in PUBLIC_WITHOUT_TOKEN:
            assert operation.get("security") == []
        else:
            assert operation.get("security") == BEARER_SECURITY


def test_openapi_declares_standard_error_responses():
    schema = _schema()
    response_components = schema["components"]["responses"]
    expected_components = {
        "DefaultError",
        "ForbiddenError",
        "NotAcceptableError",
        "NotFoundError",
        "RateLimitError",
        "UnauthorizedError",
        "UnsupportedMediaTypeError",
    }

    assert expected_components.issubset(response_components)

    for path, method, operation in _operations(schema):
        responses = operation["responses"]
        assert responses["default"] == {"$ref": "#/components/responses/DefaultError"}
        assert responses["429"] == {"$ref": "#/components/responses/RateLimitError"}

        if method in NOT_ACCEPTABLE_METHODS:
            assert responses["406"] == {"$ref": "#/components/responses/NotAcceptableError"}
        if method in NOT_FOUND_METHODS:
            assert responses["404"] == {"$ref": "#/components/responses/NotFoundError"}
        if method in BODY_METHODS and "requestBody" in operation:
            assert responses["415"] == {"$ref": "#/components/responses/UnsupportedMediaTypeError"}
        if path not in PUBLIC_WITHOUT_TOKEN:
            assert responses["401"] == {"$ref": "#/components/responses/UnauthorizedError"}
            assert responses["403"] == {"$ref": "#/components/responses/ForbiddenError"}


def test_openapi_operation_ids_are_unique():
    operation_ids = [
        operation["operationId"] for _path, _method, operation in _operations(_schema())
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_openapi_generation_emits_no_duplicate_operation_warnings():
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app.openapi()

    assert [warning for warning in caught if "Duplicate Operation ID" in str(warning.message)] == []


def test_openapi_servers_do_not_advertise_cleartext_transport():
    servers = _schema().get("servers", [])
    assert servers
    for server in servers:
        url = server["url"]
        assert url == "/" or url.startswith("https://")


def test_openapi_server_env_cleartext_falls_back_to_relative_root(monkeypatch):
    monkeypatch.setenv("OPENAPI_SERVER_URL", "http://api.example.test")

    servers = _schema().get("servers", [])

    assert servers == [{"url": "/"}]


def test_export_openapi_writes_security_contract(tmp_path):
    output_path = tmp_path / "openapi.json"

    schema = export_openapi(output_path, server_url="https://api.example.test")
    exported = json.loads(output_path.read_text(encoding="utf-8"))

    assert exported == schema
    assert exported["servers"] == [{"url": "https://api.example.test"}]
    assert exported["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    assert any(True for _ in _operations(exported))


def test_export_openapi_rejects_cleartext_server_url(tmp_path):
    output_path = tmp_path / "openapi.json"

    with pytest.raises(ValueError, match="HTTPS URL"):
        export_openapi(output_path, server_url="http://api.example.test")

    assert not output_path.exists()


def test_openapi_composed_schemas_do_not_carry_ambiguous_defaults():
    offenders: list[str] = []

    def walk(node, pointer: str = "") -> None:
        if isinstance(node, dict):
            if "default" in node and any(key in node for key in ("anyOf", "oneOf", "allOf")):
                offenders.append(pointer or "/")
            for key, value in node.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                walk(value, f"{pointer}/{escaped}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(_schema())

    assert offenders == []


def test_openapi_integer_schema_integral_bounds_are_not_floats():
    offenders: list[str] = []
    bound_keys = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
    }

    def has_integer_type(node: dict) -> bool:
        schema_type = node.get("type")
        return schema_type == "integer" or (
            isinstance(schema_type, list) and "integer" in schema_type
        )

    def walk(node, pointer: str = "") -> None:
        if isinstance(node, dict):
            if has_integer_type(node):
                for key in bound_keys:
                    value = node.get(key)
                    if isinstance(value, float) and value.is_integer():
                        offenders.append(f"{pointer or '/'}/{key}")
            for key, value in node.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                walk(value, f"{pointer}/{escaped}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(_schema())

    assert offenders == []


def _has_type(schema: dict, expected: str) -> bool:
    schema_type = schema.get("type")
    return schema_type == expected or (
        isinstance(schema_type, list) and expected in schema_type
    )


def _string_schema(schema: dict) -> dict:
    if _has_type(schema, "string"):
        return schema
    for branch in schema.get("anyOf") or []:
        if isinstance(branch, dict) and _has_type(branch, "string"):
            return branch
    return {}


def _response_schema(schema: dict, path: str, method: str, status: str = "200") -> dict:
    return schema["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]


def _resolve_schema_ref(schema: dict, node: dict) -> dict:
    ref = node.get("$ref")
    if not ref:
        return node
    prefix = "#/components/schemas/"
    assert ref.startswith(prefix)
    return schema["components"]["schemas"][ref.removeprefix(prefix)]


def _assert_dynamic_json_object(node: dict) -> None:
    assert node["type"] == "object"
    assert node["maxProperties"] == 256
    assert node["additionalProperties"]["$ref"] == "#/components/schemas/JsonValue"


def test_openapi_operation_string_parameters_are_bounded_and_patterned():
    offenders: list[str] = []

    for path, method, operation in _operations(_schema()):
        for index, parameter in enumerate(operation.get("parameters") or []):
            parameter_schema = parameter.get("schema") or {}
            if not _has_type(parameter_schema, "string"):
                continue
            if "maxLength" not in parameter_schema:
                offenders.append(f"{path} {method} parameter[{index}] missing maxLength")
            if "pattern" not in parameter_schema:
                offenders.append(f"{path} {method} parameter[{index}] missing pattern")

    assert offenders == []


def test_openapi_operation_integer_parameters_are_bounded_and_formatted():
    offenders: list[str] = []

    for path, method, operation in _operations(_schema()):
        for index, parameter in enumerate(operation.get("parameters") or []):
            parameter_schema = parameter.get("schema") or {}
            if not _has_type(parameter_schema, "integer"):
                continue
            for key in ("minimum", "maximum", "format"):
                if key not in parameter_schema:
                    offenders.append(f"{path} {method} parameter[{index}] missing {key}")

    assert offenders == []


def test_openapi_parameter_contract_uses_identifier_and_path_shapes():
    schema = _schema()

    agent_id = schema["paths"]["/api/agents/{agent_id}"]["get"]["parameters"][0]["schema"]
    assert agent_id["maxLength"] == 256
    assert agent_id["minLength"] == 1
    assert agent_id["pattern"].startswith("^[A-Za-z0-9]")

    dashscope_path = schema["paths"]["/api/dashscope/{path}"]["get"]["parameters"][0]["schema"]
    assert dashscope_path["maxLength"] == 2048
    assert dashscope_path["pattern"].endswith("{0,2048}$")

    upload_tail = schema["paths"]["/api/storage/upload-logs/{task_id}"]["get"]["parameters"][1]["schema"]
    assert upload_tail["minimum"] == 1
    assert upload_tail["maximum"] == 10_000
    assert upload_tail["format"] == "int32"


def test_openapi_auth_request_schemas_are_bounded_and_closed():
    schemas = _schema()["components"]["schemas"]

    register = schemas["RegisterRequest"]
    assert register["additionalProperties"] is False
    assert register["properties"]["email"]["maxLength"] == 254
    assert register["properties"]["password"]["maxLength"] == 1024
    assert register["properties"]["password"]["pattern"]
    assert _string_schema(register["properties"]["name"])["maxLength"] == 128

    login = schemas["LoginRequest"]
    assert login["additionalProperties"] is False
    assert login["properties"]["email"]["maxLength"] == 254
    assert login["properties"]["password"]["maxLength"] == 1024
    assert login["properties"]["password"]["pattern"]

    change_password = schemas["ChangePasswordRequest"]
    assert change_password["additionalProperties"] is False
    assert change_password["properties"]["current_password"]["maxLength"] == 1024
    assert change_password["properties"]["new_password"]["maxLength"] == 1024
    assert change_password["properties"]["confirm_password"]["maxLength"] == 1024


def test_openapi_profile_request_schemas_are_bounded_and_closed():
    schemas = _schema()["components"]["schemas"]

    active_profile = schemas["ActiveProfileRequest"]
    assert active_profile["additionalProperties"] is False
    assert _string_schema(active_profile["properties"]["id"])["maxLength"] == 256
    assert _string_schema(active_profile["properties"]["id"])["pattern"]

    config_profile = schemas["ConfigProfilePayload"]
    assert config_profile["properties"]["id"]["maxLength"] == 256
    assert config_profile["properties"]["name"]["anyOf"][0]["maxLength"] == 128
    assert config_profile["properties"]["api_key"]["anyOf"][0]["maxLength"] == 4096
    assert config_profile["properties"]["base_url"]["anyOf"][0]["maxLength"] == 4096
    assert config_profile["properties"]["hidden_models"]["anyOf"][0]["maxItems"] == 512
    assert config_profile["properties"]["saved_models"]["anyOf"][0]["maxItems"] == 512
    assert config_profile["properties"]["cached_model_count"]["anyOf"][0]["maximum"] == 10_000


def test_openapi_high_traffic_request_schemas_have_runtime_bounds():
    schema = _schema()
    schemas = schema["components"]["schemas"]

    chat = schemas["ChatRequest"]
    assert chat["additionalProperties"] is False
    assert chat["properties"]["messages"]["maxItems"] == 128
    assert _string_schema(chat["properties"]["message"])["maxLength"] == 200_000
    chat_attachments = chat["properties"]["attachments"]["anyOf"][0]
    assert chat_attachments["maxItems"] == 32

    chat_options = schemas["ChatOptions"]
    temperature = chat_options["properties"]["temperature"]["anyOf"][0]
    assert temperature["minimum"] == 0
    assert temperature["maximum"] == 2
    max_tokens = chat_options["properties"]["max_tokens"]["anyOf"][0]
    assert max_tokens["minimum"] == 1
    assert max_tokens["maximum"] == 1_000_000

    workflow = schemas["WorkflowExecuteRequest"]
    assert workflow["additionalProperties"] is False
    assert workflow["properties"]["nodes"]["minItems"] == 1
    assert workflow["properties"]["nodes"]["maxItems"] == 500
    assert workflow["properties"]["edges"]["maxItems"] == 2000

    live_query = schemas["QueryRequest"]
    assert live_query["properties"]["input"]["maxLength"] == 200_000
    assert live_query["properties"]["input"]["minLength"] == 1
    assert _string_schema(live_query["properties"]["agent_id"])["maxLength"] == 256

    create_agent = schemas["CreateAgentRequest"]
    assert create_agent["additionalProperties"] is False
    assert create_agent["properties"]["provider_id"]["maxLength"] == 256
    assert "minLength" not in create_agent["properties"]["provider_id"]
    assert "minLength" not in create_agent["properties"]["model_id"]
    assert create_agent["properties"]["temperature"]["anyOf"][0]["maximum"] == 2
    assert create_agent["properties"]["max_tokens"]["anyOf"][0]["maximum"] == 1_000_000

    inline_table = schemas["InlineTableAnalysisRequest"]
    assert inline_table["properties"]["file_name"]["maxLength"] == 512
    assert inline_table["properties"]["content"]["maxLength"] == 28_000_000
    assert inline_table["properties"]["sample_rows"]["maximum"] == 100
    assert inline_table["properties"]["csv_encoding"]["maxLength"] == 64

    pull_model = schemas["PullModelRequest"]
    assert pull_model["properties"]["model"]["maxLength"] == 256
    assert pull_model["properties"]["base_url"]["maxLength"] == 4096

    pdf_body = _resolve_schema_ref(
        schema,
        schema["paths"]["/api/pdf/extract"]["post"]["requestBody"]["content"][
            "multipart/form-data"
        ]["schema"],
    )
    assert pdf_body["properties"]["template_type"]["maxLength"] == 128
    assert pdf_body["properties"]["api_key"]["maxLength"] == 4096
    assert pdf_body["properties"]["additional_instructions"]["maxLength"] == 100_000
    assert pdf_body["properties"]["model_id"]["maxLength"] == 256

    personas_body = schema["paths"]["/api/personas"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert personas_body["maxItems"] == 10_000

    vertex_update = schemas["VertexAIConfigUpdateRequest"]
    assert vertex_update["properties"]["gemini_api_key"]["anyOf"][0]["maxLength"] == 4096
    assert vertex_update["properties"]["vertex_ai_project_id"]["anyOf"][0]["maxLength"] == 256
    assert vertex_update["properties"]["vertex_ai_credentials_json"]["anyOf"][0]["maxLength"] == 100_000
    assert vertex_update["properties"]["hidden_models"]["anyOf"][0]["maxItems"] == 512
    assert vertex_update["properties"]["saved_models"]["anyOf"][0]["maxItems"] == 512

    search_query = schema["paths"]["/api/search"]["post"]["parameters"][0]["schema"]
    assert search_query["minLength"] == 1
    assert search_query["maxLength"] == 4096


def test_openapi_multi_agent_request_schemas_have_runtime_bounds():
    schemas = _schema()["components"]["schemas"]

    orchestrate = schemas["OrchestrateRequest"]
    assert orchestrate["additionalProperties"] is False
    assert orchestrate["properties"]["agent_ids"]["anyOf"][0]["maxItems"] == 64

    live_run = schemas["ADKLiveRunRequest"]
    assert live_run["additionalProperties"] is False
    assert live_run["properties"]["live_requests"]["anyOf"][0]["maxItems"] == 64
    assert live_run["properties"]["max_events"]["anyOf"][0]["minimum"] == 1
    assert live_run["properties"]["max_events"]["anyOf"][0]["maximum"] == 1000

    confirmation = schemas["ADKToolConfirmationRequest"]
    assert confirmation["additionalProperties"] is False
    payload_branches = confirmation["properties"]["payload"]["anyOf"]
    assert {"object", "array", "string", "integer", "number", "boolean"}.issubset(
        {branch.get("type") for branch in payload_branches}
    )
    ticket_timestamp = confirmation["properties"]["ticketTimestampMs"]["anyOf"][0]
    assert ticket_timestamp["minimum"] == 0
    assert ticket_timestamp["maximum"] == 4_102_444_800_000

    memory_search = schemas["ADKMemorySearchRequest"]
    assert memory_search["additionalProperties"] is False
    assert memory_search["properties"]["limit"]["anyOf"][0]["minimum"] == 1
    assert memory_search["properties"]["limit"]["anyOf"][0]["maximum"] == 1000

    sheet_stage = schemas["SheetStageProtocolRequest"]
    assert sheet_stage["additionalProperties"] is False
    assert sheet_stage["properties"]["sampleRows"]["anyOf"][0]["minimum"] == 1
    assert sheet_stage["properties"]["sampleRows"]["anyOf"][0]["maximum"] == 1000
    assert sheet_stage["properties"]["sheetName"]["anyOf"][0]["maximum"] == 10_000


def test_openapi_multi_agent_success_responses_are_typed_and_bounded():
    schema = _schema()

    _assert_dynamic_json_object(
        schema["components"]["schemas"]["MultiAgentDynamicObjectResponse"]
    )

    for path, method in (
        ("/api/multi-agent/orchestrate", "post"),
        ("/api/multi-agent/agents/register", "post"),
        ("/api/multi-agent/adk/agents/{agent_id}/sessions/{session_id}/rewind", "post"),
        (
            "/api/multi-agent/agents/{agent_id}/runtime/sessions/{session_id}/rewind",
            "post",
        ),
        ("/api/multi-agent/workflows/excel-analysis/stage", "post"),
        ("/api/multi-agent/workflows/excel-analysis/stage/lineage", "get"),
        ("/api/multi-agent/workflows/image-edit", "post"),
        ("/api/multi-agent/workflows/excel-analysis", "post"),
        ("/api/multi-agent/workflows/adk-samples/import", "post"),
    ):
        dynamic_response = _resolve_schema_ref(schema, _response_schema(schema, path, method))
        _assert_dynamic_json_object(dynamic_response)

    agent_list = _resolve_schema_ref(schema, _response_schema(schema, "/api/multi-agent/agents", "get"))
    assert agent_list["properties"]["agents"]["maxItems"] == 10_000
    _assert_dynamic_json_object(agent_list["properties"]["agents"]["items"])
    assert agent_list["properties"]["count"]["maximum"] == 10_000

    run_response = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/multi-agent/agents/{agent_id}/runtime/run", "post")
    )
    assert _resolve_schema_ref(
        schema, _response_schema(schema, "/api/multi-agent/adk/agents/{agent_id}/run", "post")
    ) == run_response
    assert _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/multi-agent/agents/{agent_id}/runtime/sessions/{session_id}/confirm-tool",
            "post",
        ),
    ) == run_response
    assert _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/multi-agent/adk/agents/{agent_id}/sessions/{session_id}/confirm-tool",
            "post",
        ),
    ) == run_response
    assert run_response["properties"]["output"]["maxLength"] == 1_000_000
    assert run_response["properties"]["usage"]["maxProperties"] == 64
    assert run_response["properties"]["event_count"]["maximum"] == 10_000
    assert run_response["properties"]["actions"]["maxProperties"] == 256
    assert run_response["properties"]["long_running_tool_ids"]["maxItems"] == 128

    live_run_response = _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/multi-agent/agents/{agent_id}/runtime/run-live", "post"),
    )
    assert _resolve_schema_ref(
        schema, _response_schema(schema, "/api/multi-agent/adk/agents/{agent_id}/run-live", "post")
    ) == live_run_response
    assert live_run_response["properties"]["events"]["maxItems"] == 1000
    _assert_dynamic_json_object(live_run_response["properties"]["events"]["items"])

    session_list = _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/multi-agent/agents/{agent_id}/runtime/sessions", "get"),
    )
    assert _resolve_schema_ref(
        schema, _response_schema(schema, "/api/multi-agent/adk/agents/{agent_id}/sessions", "get")
    ) == session_list
    assert session_list["properties"]["sessions"]["maxItems"] == 10_000
    _assert_dynamic_json_object(session_list["properties"]["sessions"]["items"])
    assert session_list["properties"]["count"]["maximum"] == 10_000

    session_detail = _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/multi-agent/agents/{agent_id}/runtime/sessions/{session_id}",
            "get",
        ),
    )
    assert _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/multi-agent/adk/agents/{agent_id}/sessions/{session_id}",
            "get",
        ),
    ) == session_detail
    _assert_dynamic_json_object(session_detail["properties"]["session"])

    memory_index = _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/multi-agent/agents/{agent_id}/runtime/sessions/{session_id}/memory/index",
            "post",
        ),
    )
    assert _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/multi-agent/adk/agents/{agent_id}/sessions/{session_id}/memory/index",
            "post",
        ),
    ) == memory_index
    assert memory_index["properties"]["memories"]["maxItems"] == 10_000
    _assert_dynamic_json_object(memory_index["properties"]["memories"]["items"])
    assert memory_index["properties"]["count"]["maximum"] == 10_000

    memory_search = _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/multi-agent/agents/{agent_id}/runtime/memory/search", "post"),
    )
    assert _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/multi-agent/adk/agents/{agent_id}/memory/search", "post"),
    ) == memory_search
    assert memory_search["properties"]["query"]["maxLength"] == 4096
    assert memory_search["properties"]["memories"]["maxItems"] == 1000
    _assert_dynamic_json_object(memory_search["properties"]["memories"]["items"])
    assert memory_search["properties"]["count"]["maximum"] == 1000

    samples_templates = _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/multi-agent/workflows/adk-samples/templates", "get"),
    )
    assert _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/multi-agent/workflows/adk-samples/import-all", "post"),
    ) == samples_templates
    assert samples_templates["properties"]["templates"]["maxItems"] == 1000
    _assert_dynamic_json_object(samples_templates["properties"]["templates"]["items"])
    assert samples_templates["properties"]["count"]["maximum"] == 1000


def test_openapi_workflow_success_responses_are_typed_and_bounded():
    schema = _schema()

    _assert_dynamic_json_object(schema["components"]["schemas"]["WorkflowDynamicObjectResponse"])

    execute = _resolve_schema_ref(schema, _response_schema(schema, "/api/workflows/execute", "post"))
    assert execute["properties"]["execution_id"]["maxLength"] == 256
    assert execute["properties"]["status"]["maxLength"] == 32
    assert execute["properties"]["events"]["maxItems"] == 10_000
    _assert_dynamic_json_object(execute["properties"]["events"]["items"])
    assert execute["properties"]["resultPreviewAudioUrls"]["maxItems"] == 10_000
    assert execute["properties"]["resultPreviewVideoUrls"]["maxItems"] == 10_000

    state = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/{execution_id}/state", "get")
    )
    assert state["properties"]["executionId"]["maxLength"] == 256
    assert state["properties"]["nodeStatuses"]["maxProperties"] == 10_000
    assert state["properties"]["nodeProgress"]["maxProperties"] == 10_000
    assert state["properties"]["nodeResults"]["maxProperties"] == 10_000
    assert state["properties"]["nodeResults"]["additionalProperties"]["$ref"] == (
        "#/components/schemas/JsonValue"
    )
    assert state["properties"]["stateVersion"]["maximum"] == 4_102_444_800_000

    debug_runtime = _resolve_schema_ref(
        schema,
        _response_schema(
            schema,
            "/api/workflows/{execution_id}/debug/execution-state-runtime",
            "get",
        ),
    )
    _assert_dynamic_json_object(debug_runtime["properties"]["execution_state_runtime"])

    history = _resolve_schema_ref(schema, _response_schema(schema, "/api/workflows/history", "get"))
    assert history["properties"]["executions"]["maxItems"] == 100
    assert history["properties"]["count"]["maximum"] == 100
    assert history["properties"]["total"]["maximum"] == 1_000_000
    assert history["properties"]["limit"]["maximum"] == 100

    history_detail = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/history/{execution_id}", "get")
    )
    assert history_detail["properties"]["node_executions"]["maxItems"] == 10_000
    assert history_detail["properties"]["task"]["maxLength"] == 100_000
    _assert_dynamic_json_object(history_detail["properties"]["meta"])

    for path, method in (
        ("/api/workflows/history/{execution_id}/images/preview", "get"),
        ("/api/workflows/history/{execution_id}/audio/preview", "get"),
        ("/api/workflows/history/{execution_id}/video/preview", "get"),
        ("/api/workflows/mode-presets/{mode_id}", "get"),
        ("/api/workflows/templates", "post"),
        ("/api/workflows/template-categories", "post"),
        ("/api/workflows/templates/{template_id}", "get"),
        ("/api/workflows/templates/{template_id}/copy", "post"),
        ("/api/workflows/templates/{template_id}", "put"),
    ):
        dynamic_response = _resolve_schema_ref(schema, _response_schema(schema, path, method))
        _assert_dynamic_json_object(dynamic_response)

    rebuild = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/templates/rebuild", "post")
    )
    assert rebuild["properties"]["deleted_count"]["maximum"] == 10_000
    assert rebuild["properties"]["created_count"]["maximum"] == 10_000
    assert rebuild["properties"]["templates"]["maxItems"] == 10_000
    _assert_dynamic_json_object(rebuild["properties"]["templates"]["items"])

    reset = _resolve_schema_ref(schema, _response_schema(schema, "/api/workflows/reset", "post"))
    reset_history = _resolve_schema_ref(schema, reset["properties"]["history"])
    assert reset_history["properties"]["execution_deleted_count"]["maximum"] == 1_000_000
    reset_templates = _resolve_schema_ref(schema, reset["properties"]["templates"])
    assert reset_templates["properties"]["items"]["maxItems"] == 10_000
    _assert_dynamic_json_object(reset_templates["properties"]["items"]["items"])

    mode_presets = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/mode-presets", "get")
    )
    assert mode_presets["properties"]["items"]["maxItems"] == 64
    assert mode_presets["properties"]["count"]["maximum"] == 64

    template_list = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/templates", "get")
    )
    assert template_list["properties"]["templates"]["maxItems"] == 10_000
    _assert_dynamic_json_object(template_list["properties"]["templates"]["items"])
    assert template_list["properties"]["count"]["maximum"] == 10_000

    categories = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/template-categories", "get")
    )
    assert categories["properties"]["categories"]["maxItems"] == 1000
    assert categories["properties"]["count"]["maximum"] == 1000

    coverage = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/templates/coverage", "get")
    )
    _assert_dynamic_json_object(coverage["properties"]["coverage"])
    coverage_templates = _resolve_schema_ref(schema, coverage["properties"]["templates"])
    assert coverage_templates["properties"]["count"]["maximum"] == 10_000

    seed = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/templates/seed", "post")
    )
    assert seed["properties"]["created_count"]["maximum"] == 10_000
    assert seed["properties"]["templates"]["maxItems"] == 10_000
    _assert_dynamic_json_object(seed["properties"]["templates"]["items"])

    for path, method, media_type, expected_format, max_length in (
        (
            "/api/workflows/{execution_id}/status",
            "get",
            "text/event-stream",
            None,
            1_000_000,
        ),
        (
            "/api/workflows/history/{execution_id}/images/download",
            "get",
            "application/zip",
            "binary",
            536_870_912,
        ),
        (
            "/api/workflows/history/{execution_id}/audio/download",
            "get",
            "application/zip",
            "binary",
            536_870_912,
        ),
        (
            "/api/workflows/history/{execution_id}/video/download",
            "get",
            "application/zip",
            "binary",
            536_870_912,
        ),
        (
            "/api/workflows/history/{execution_id}/audio/items/{item_index}",
            "get",
            "application/octet-stream",
            "binary",
            67_108_864,
        ),
        (
            "/api/workflows/history/{execution_id}/video/items/{item_index}",
            "get",
            "application/octet-stream",
            "binary",
            134_217_728,
        ),
        (
            "/api/workflows/history/{execution_id}/analysis/download",
            "get",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "binary",
            536_870_912,
        ),
    ):
        content = schema["paths"][path][method]["responses"]["200"]["content"]
        assert set(content) == {media_type}
        media_schema = content[media_type]["schema"]
        assert media_schema["type"] == "string"
        assert media_schema["maxLength"] == max_length
        if expected_format:
            assert media_schema["format"] == expected_format


def test_openapi_mode_request_schema_has_generation_bounds():
    schemas = _schema()["components"]["schemas"]

    mode_request = schemas["ModeRequest"]
    assert mode_request["additionalProperties"] is False
    assert mode_request["properties"]["attachments"]["anyOf"][0]["maxItems"] == 32
    assert _string_schema(mode_request["properties"]["prompt"])["maxLength"] == 200_000

    mode_options = schemas["ModeOptions"]
    assert mode_options["additionalProperties"] is True
    assert mode_options["properties"]["temperature"]["anyOf"][0]["maximum"] == 2
    assert mode_options["properties"]["max_tokens"]["anyOf"][0]["maximum"] == 1_000_000
    assert mode_options["properties"]["segmentation_classes"]["anyOf"][0]["maxItems"] == 32
    assert mode_options["properties"]["source_image"]["anyOf"][0]["maxLength"] == 4096
    assert mode_options["properties"]["storyboard_segments"]["anyOf"][0]["maxItems"] == 32
    assert mode_options["properties"]["canvas_w"]["anyOf"][0]["minimum"] == 64
    assert mode_options["properties"]["canvas_w"]["anyOf"][0]["maximum"] == 8192
    assert mode_options["properties"]["number_of_images"]["anyOf"][0]["maximum"] == 8


def test_openapi_public_health_and_auth_success_responses_are_typed():
    schema = _schema()

    assert "/" not in schema["paths"]

    health = _resolve_schema_ref(schema, _response_schema(schema, "/health", "get"))
    assert health["properties"]["status"]["maxLength"] == 32
    assert health["properties"]["version"]["maxLength"] == 32

    auth_config = _resolve_schema_ref(schema, _response_schema(schema, "/api/auth/config", "get"))
    assert auth_config["properties"]["allow_registration"]["type"] == "boolean"

    ip_info = _resolve_schema_ref(schema, _response_schema(schema, "/api/auth/ip-info", "get"))
    assert ip_info["properties"]["detected_ip"]["maxLength"] == 128
    assert ip_info["properties"]["is_private"]["type"] == "boolean"

    logout = _resolve_schema_ref(schema, _response_schema(schema, "/api/auth/logout", "post"))
    assert logout["properties"]["message"]["maxLength"] == 128

    refresh = _resolve_schema_ref(schema, _response_schema(schema, "/api/auth/refresh", "post"))
    assert refresh["properties"]["expires_in"]["minimum"] == 1
    assert refresh["properties"]["has_active_profile"]["type"] == "boolean"

    current_user = _resolve_schema_ref(schema, _response_schema(schema, "/api/auth/me", "get"))
    assert current_user["properties"]["id"]["type"] == "string"
    assert current_user["properties"]["has_active_profile"]["type"] == "boolean"

    multi_agent_health = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/multi-agent/health", "get")
    )
    assert multi_agent_health["properties"]["status"]["maxLength"] == 32
    assert multi_agent_health["properties"]["message"]["maxLength"] == 128

    execution_policy = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/execution-policy", "get")
    )
    assert execution_policy["properties"]["sse_idle_threshold_ms"]["minimum"] == 100
    assert execution_policy["properties"]["polling_interval_ms"]["minimum"] == 100
    assert execution_policy["properties"]["hard_timeout_ms"]["maximum"] == 86_400_000

    model_cache_clear = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/models/cache", "delete")
    )
    assert model_cache_clear["properties"]["message"]["maxLength"] == 128
    assert model_cache_clear["properties"]["redis_keys_deleted"]["minimum"] == 0
    assert model_cache_clear["properties"]["pattern"]["maxLength"] == 512

    model_cache_status = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/models/cache/status", "get")
    )
    assert model_cache_status["type"] == "object"
    model_cache_entry = _resolve_schema_ref(schema, model_cache_status["additionalProperties"])
    assert model_cache_entry["properties"]["model_count"]["maximum"] == 10_000
    assert model_cache_entry["properties"]["expires_in_seconds"]["maximum"] == 3600

    model_list = _resolve_schema_ref(schema, _response_schema(schema, "/api/models/{provider}", "get"))
    assert model_list["properties"]["models"]["maxItems"] == 10_000
    assert model_list["properties"]["mode_catalog"]["maxItems"] == 512
    assert model_list["properties"]["provider"]["maxLength"] == 128
    model_config = _resolve_schema_ref(schema, model_list["properties"]["models"]["items"])
    assert model_config["properties"]["id"]["maxLength"] == 256
    assert model_config["properties"]["description"]["maxLength"] == 10_000
    assert model_config["properties"]["context_window"]["anyOf"][0]["maximum"] == 10_000_000

    mode_controls = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/modes/{provider}/{mode}/controls", "get")
    )
    assert mode_controls["properties"]["provider"]["maxLength"] == 128
    assert mode_controls["properties"]["mode"]["maxLength"] == 128
    assert mode_controls["properties"]["schema"]["type"] == "object"

    mode_capabilities = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/modes/{provider}/capabilities", "get")
    )
    assert mode_capabilities["properties"]["capabilities"]["maxItems"] == 512
    mode_capability = _resolve_schema_ref(
        schema, mode_capabilities["properties"]["capabilities"]["items"]
    )
    assert mode_capability["properties"]["id"]["maxLength"] == 128
    assert mode_capability["properties"]["reason"]["anyOf"][0]["maxLength"] == 512

    mode_response = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/modes/{provider}/{mode}", "post")
    )
    assert mode_response["properties"]["provider"]["maxLength"] == 128
    assert mode_response["properties"]["mode"]["maxLength"] == 128

    mode_stream_content = schema["paths"]["/api/modes/{provider}/{mode}/stream"]["post"][
        "responses"
    ]["200"]["content"]
    assert set(mode_stream_content) == {"text/event-stream"}
    assert mode_stream_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    chat_content = schema["paths"]["/api/modes/{provider}/chat"]["post"]["responses"]["200"][
        "content"
    ]
    assert set(chat_content) == {"application/json", "text/event-stream"}
    chat_response = _resolve_schema_ref(schema, chat_content["application/json"]["schema"])
    assert chat_response["additionalProperties"] is True
    assert chat_response["properties"]["text"]["anyOf"][0]["maxLength"] == 1_000_000
    assert chat_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    research_stream_policy = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/research/stream/policy", "get")
    )
    assert research_stream_policy["properties"]["idle_timeout_ms"]["maximum"] == 3_600_000
    assert research_stream_policy["properties"]["max_recovery_attempts"]["maximum"] == 100

    research_stream_start_content = schema["paths"]["/api/research/stream/start"]["post"][
        "responses"
    ]["200"]["content"]
    assert set(research_stream_start_content) == {"application/json", "text/event-stream"}
    research_stream_interaction = _resolve_schema_ref(
        schema, research_stream_start_content["application/json"]["schema"]
    )
    assert research_stream_interaction["properties"]["interaction_id"]["maxLength"] == 512
    assert (
        research_stream_start_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000
    )

    research_stream_action = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/research/stream/action", "post")
    )
    assert research_stream_action == research_stream_interaction

    research_stream_event_content = schema["paths"]["/api/research/stream/{interaction_id}"][
        "get"
    ]["responses"]["200"]["content"]
    assert set(research_stream_event_content) == {"text/event-stream"}
    assert research_stream_event_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    research_stream_status = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/research/stream/status/{interaction_id}", "get")
    )
    assert research_stream_status["properties"]["interaction_id"]["maxLength"] == 512
    assert _string_schema(research_stream_status["properties"]["status"])["maxLength"] == 64
    assert research_stream_status["properties"]["outputs"]["maxItems"] == 10_000
    assert research_stream_status["properties"]["outputs"]["items"]["$ref"] == (
        "#/components/schemas/JsonValue"
    )
    assert any(
        branch.get("$ref") == "#/components/schemas/JsonValue"
        for branch in research_stream_status["properties"]["error"]["anyOf"]
    )

    research_stream_cancel = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/research/stream/cancel/{interaction_id}", "post")
    )
    assert research_stream_cancel["properties"]["interaction_id"]["maxLength"] == 512
    assert research_stream_cancel["properties"]["status"]["maxLength"] == 64

    embedding_add = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/embedding/add-document", "post")
    )
    assert embedding_add["properties"]["success"]["type"] == "boolean"
    assert _string_schema(embedding_add["properties"]["document_id"])["maxLength"] == 256
    assert _string_schema(embedding_add["properties"]["error"])["maxLength"] == 4096

    embedding_search = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/embedding/search", "post")
    )
    assert embedding_search["properties"]["results"]["maxItems"] == 1_000
    embedding_search_result = _resolve_schema_ref(schema, embedding_search["properties"]["results"]["items"])
    assert embedding_search_result["properties"]["similarity"]["maximum"] == 1

    embedding_documents = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/embedding/documents", "get")
    )
    assert embedding_documents["properties"]["documents"]["maxItems"] == 1_000_000
    embedding_stats = _resolve_schema_ref(schema, embedding_documents["properties"]["stats"])
    assert embedding_stats["properties"]["total_chunks"]["maximum"] == 10_000_000

    embedding_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/embedding/document/{document_id}", "delete")
    )
    assert embedding_delete["properties"]["message"]["maxLength"] == 128

    file_search_upload = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/file-search/upload", "post")
    )
    assert file_search_upload["properties"]["file_search_store_name"]["maxLength"] == 512
    assert file_search_upload["properties"]["operation"]["maxLength"] == 512

    file_search_stores = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/file-search/stores", "get")
    )
    assert file_search_stores["properties"]["stores"]["maxItems"] == 10_000
    file_search_store = _resolve_schema_ref(schema, file_search_stores["properties"]["stores"]["items"])
    assert file_search_store["properties"]["display_name"]["maxLength"] == 256
    assert _string_schema(file_search_store["properties"]["create_time"])["maxLength"] == 128

    init_critical = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/init/critical", "get")
    )
    assert init_critical["properties"]["profiles"]["maxItems"] == 10_000
    assert _string_schema(init_critical["properties"]["active_profile_id"])["maxLength"] == 256
    assert init_critical["properties"]["cached_mode_catalog"]["maxItems"] == 128

    init_more_sessions = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/init/sessions/more", "get")
    )
    assert init_more_sessions["properties"]["sessions"]["maxItems"] == 50
    assert init_more_sessions["properties"]["total"]["anyOf"][0]["maximum"] == 10_000_000
    assert init_more_sessions["properties"]["hasMore"]["type"] == "boolean"

    init_non_critical = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/init/non-critical", "get")
    )
    assert init_non_critical["properties"]["sessions"]["maxItems"] == 20
    assert init_non_critical["properties"]["sessionsTotal"]["maximum"] == 10_000_000
    assert init_non_critical["properties"]["storageConfigs"]["maxItems"] == 10_000

    init_legacy = _resolve_schema_ref(schema, _response_schema(schema, "/api/init", "get"))
    assert init_legacy["properties"]["profiles"]["maxItems"] == 10_000
    assert init_legacy["properties"]["sessions"]["maxItems"] == 10_000
    init_metadata = _resolve_schema_ref(schema, init_legacy["properties"]["_metadata"])
    assert init_metadata["properties"]["timestamp"]["maximum"] == 4_102_444_800_000

    session_list = _resolve_schema_ref(schema, _response_schema(schema, "/api/sessions", "get"))
    assert session_list["type"] == "array"
    assert session_list["maxItems"] == 10_000
    session_detail = _resolve_schema_ref(schema, session_list["items"])
    assert _resolve_schema_ref(schema, _response_schema(schema, "/api/sessions", "post")) == (
        session_detail
    )
    assert _resolve_schema_ref(
        schema, _response_schema(schema, "/api/sessions/{session_id}", "get")
    ) == session_detail
    assert session_detail["properties"]["id"]["maxLength"] == 512
    assert session_detail["properties"]["title"]["maxLength"] == 512
    assert session_detail["properties"]["created_at"]["maximum"] == 4_102_444_800_000
    assert session_detail["properties"]["messages"]["maxItems"] == 10_000
    session_message = session_detail["properties"]["messages"]["items"]
    assert session_message["maxProperties"] == 256
    assert session_message["additionalProperties"]["$ref"] == "#/components/schemas/JsonValue"

    session_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/sessions/{session_id}", "delete")
    )
    assert session_delete["properties"]["success"]["type"] == "boolean"

    session_history_states = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/sessions/{session_id}/history-states", "get")
    )
    assert session_history_states["properties"]["states"]["maxItems"] == 10_000
    session_history_state = _resolve_schema_ref(
        schema, session_history_states["properties"]["states"]["items"]
    )
    assert session_history_state["properties"]["message_id"]["maxLength"] == 512
    assert session_history_state["properties"]["updated_at"]["maximum"] == 4_102_444_800_000
    assert _resolve_schema_ref(
        schema,
        _response_schema(
            schema, "/api/sessions/{session_id}/history-states/{message_id}", "patch"
        ),
    ) == session_history_state

    session_history_pref = _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/sessions/{session_id}/history-preferences", "get"),
    )
    assert session_history_pref["properties"]["show_favorites_only"]["type"] == "boolean"
    assert session_history_pref["properties"]["updated_at"]["anyOf"][0]["maximum"] == (
        4_102_444_800_000
    )
    assert _resolve_schema_ref(
        schema,
        _response_schema(schema, "/api/sessions/{session_id}/history-preferences", "patch"),
    ) == session_history_pref

    session_attachment = _resolve_schema_ref(
        schema,
        _response_schema(
            schema, "/api/sessions/{session_id}/attachments/{attachment_id}", "get"
        ),
    )
    assert session_attachment["properties"]["url"]["anyOf"][0]["maxLength"] == 4096
    assert session_attachment["properties"]["upload_status"]["anyOf"][0]["maxLength"] == 64
    assert session_attachment["properties"]["size"]["anyOf"][0]["maximum"] == 10_000_000_000

    browser_stop = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/browser/stop", "post")
    )
    assert browser_stop["properties"]["success"]["type"] == "boolean"
    assert browser_stop["properties"]["message"]["maxLength"] == 640

    browser_sessions = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/browser/sessions", "get")
    )
    assert browser_sessions["properties"]["sessions"]["maxItems"] == 10_000
    assert browser_sessions["properties"]["count"]["maximum"] == 10_000

    browse_progress_content = schema["paths"]["/api/browse/progress/{operation_id}"]["get"]["responses"]["200"]["content"]
    assert set(browse_progress_content) == {"text/event-stream"}
    assert browse_progress_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    interaction_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/interactions/{interaction_id}", "delete")
    )
    assert interaction_delete["properties"]["message"]["maxLength"] == 128

    interaction_stream_content = schema["paths"]["/api/interactions/{interaction_id}/stream"]["get"][
        "responses"
    ]["200"]["content"]
    assert set(interaction_stream_content) == {"text/event-stream"}
    assert interaction_stream_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    live_query = _resolve_schema_ref(schema, _response_schema(schema, "/api/live/query", "post"))
    assert live_query["properties"]["output"]["maxLength"] == 1_000_000
    assert live_query["properties"]["status"]["maxLength"] == 32
    assert _string_schema(live_query["properties"]["agent_id"])["maxLength"] == 256
    assert live_query["properties"]["event_count"]["anyOf"][0]["maximum"] == 10_000
    assert live_query.get("additionalProperties") is not True

    live_stream_content = schema["paths"]["/api/live/stream-query"]["post"]["responses"]["200"][
        "content"
    ]
    assert set(live_stream_content) == {"text/event-stream"}
    assert live_stream_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    personas_reset = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/personas/reset", "post")
    )
    assert personas_reset["properties"]["count"]["maximum"] == 10_000
    assert personas_reset["properties"]["message"]["maxLength"] == 128

    personas_list = _response_schema(schema, "/api/personas", "get")
    assert personas_list["type"] == "array"
    persona_item = _resolve_schema_ref(schema, personas_list["items"])
    assert persona_item["properties"]["id"]["maxLength"] == 256
    assert persona_item["properties"]["system_prompt"]["maxLength"] == 100_000

    worker_pool_health = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/worker-pool/health", "get")
    )
    assert worker_pool_health["properties"]["num_workers"]["maximum"] == 1024
    assert worker_pool_health["properties"]["pending_tasks_count"]["maximum"] == 1_000_000
    assert _string_schema(worker_pool_health["properties"]["error"])["maxLength"] == 256

    storage_active = _resolve_schema_ref(schema, _response_schema(schema, "/api/storage/active", "get"))
    assert _string_schema(storage_active["properties"]["storage_id"])["maxLength"] == 256

    storage_configs = _response_schema(schema, "/api/storage/configs", "get")
    assert storage_configs["type"] == "array"
    assert storage_configs["items"]["type"] == "object"

    for path, method in (
        ("/api/storage/configs", "post"),
        ("/api/storage/configs/{config_id}", "put"),
        ("/api/storage/active/browse", "get"),
        ("/api/storage/browse/{storage_id}", "get"),
        ("/api/storage/items/delete", "post"),
        ("/api/storage/items/rename", "post"),
        ("/api/storage/test", "post"),
        ("/api/storage/upload", "post"),
    ):
        storage_dynamic = _resolve_schema_ref(schema, _response_schema(schema, path, method))
        assert storage_dynamic["maxProperties"] == 256
        assert storage_dynamic["additionalProperties"]["$ref"] == "#/components/schemas/JsonValue"

    storage_config_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/configs/{config_id}", "delete")
    )
    assert storage_config_delete["properties"]["success"]["type"] == "boolean"
    assert storage_config_delete["properties"]["storage_revision"]["maximum"] == 10_000_000_000

    storage_set_active = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/active/{storage_id}", "post")
    )
    assert storage_set_active["properties"]["storage_id"]["maxLength"] == 256
    assert storage_set_active["properties"]["storage_revision"]["maximum"] == 10_000_000_000

    storage_metadata_batch = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/metadata/batch", "post")
    )
    assert storage_metadata_batch["properties"]["items"]["maxItems"] == 100
    assert storage_metadata_batch["properties"]["items"]["items"]["maxProperties"] == 256
    assert storage_metadata_batch["properties"]["total"]["maximum"] == 100

    storage_batch_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/items/batch-delete", "post")
    )
    assert storage_batch_delete["properties"]["results"]["maxItems"] == 1000
    assert storage_batch_delete["properties"]["failure_count"]["maximum"] == 1000

    storage_upload_queue = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/upload-async", "post")
    )
    assert _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/upload-from-url", "post")
    ) == storage_upload_queue
    assert _string_schema(storage_upload_queue["properties"]["task_id"])["maxLength"] == 512
    assert storage_upload_queue["properties"]["queue_position"]["minimum"] == -1
    assert storage_upload_queue["properties"]["queue_position"]["maximum"] == 1_000_000

    storage_upload_status = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/upload-status/{task_id}", "get")
    )
    assert storage_upload_status["properties"]["filename"]["maxLength"] == 512
    assert storage_upload_status["properties"]["created_at"]["maximum"] == 4_102_444_800_000
    assert _string_schema(storage_upload_status["properties"]["target_url"])["maxLength"] == 4096

    storage_upload_task_db = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/upload-task-db/{task_id}", "get")
    )
    assert _resolve_schema_ref(schema, storage_upload_task_db["properties"]["task"]) == (
        storage_upload_status
    )

    storage_upload_logs = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/upload-logs/{task_id}", "get")
    )
    assert storage_upload_logs["properties"]["task_id"]["maxLength"] == 512
    assert storage_upload_logs["properties"]["logs"]["maxItems"] == 10_000

    storage_retry = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/retry-upload/{task_id}", "post")
    )
    assert storage_retry["properties"]["queue_position"]["maximum"] == 1_000_000

    storage_download_prepare = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/items/downloads", "post")
    )
    assert storage_download_prepare["properties"]["download_url"]["maxLength"] == 4096
    assert storage_download_prepare["properties"]["total_files"]["maximum"] == 500
    assert storage_download_prepare["properties"]["expires_at"]["maximum"] == 4_102_444_800_000

    for path in (
        "/api/storage/downloads/{download_id}",
        "/api/storage/download",
        "/api/storage/preview",
    ):
        storage_binary_content = schema["paths"][path]["get"]["responses"]["200"]["content"]
        assert "application/json" not in storage_binary_content
        assert storage_binary_content["application/octet-stream"]["schema"]["format"] == "binary"
        assert (
            storage_binary_content["application/octet-stream"]["schema"]["maxLength"]
            == 536_870_912
        )

    storage_debug = _resolve_schema_ref(schema, _response_schema(schema, "/api/storage/debug", "get"))
    assert storage_debug["properties"]["module_file"]["maxLength"] == 4096
    assert storage_debug["properties"]["backend_env_exists"]["type"] == "boolean"
    debug_features = _resolve_schema_ref(schema, storage_debug["properties"]["features"])
    assert debug_features["properties"]["upload_async"]["type"] == "boolean"

    storage_worker_status = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/storage/worker-status", "get")
    )
    worker_status_pool = _resolve_schema_ref(schema, storage_worker_status["properties"]["worker_pool"])
    assert worker_status_pool["properties"]["workers_total"]["maximum"] == 1024
    assert worker_status_pool["properties"]["workers_alive"]["maximum"] == 1024
    worker_status_server = _resolve_schema_ref(schema, storage_worker_status["properties"]["server"])
    assert worker_status_server["properties"]["pid"]["maximum"] == 10_000_000

    workflow_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/history/{execution_id}", "delete")
    )
    assert workflow_delete["properties"]["success"]["type"] == "boolean"

    workflow_clear = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/history", "delete")
    )
    assert workflow_clear["properties"]["execution_deleted_count"]["maximum"] == 1_000_000
    assert workflow_clear["properties"]["node_deleted_count"]["maximum"] == 10_000_000

    admin_config = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/system/admin/config", "get")
    )
    admin_values = _resolve_schema_ref(schema, admin_config["properties"]["values"])
    assert admin_values["properties"]["maxLoginAttempts"]["maximum"] == 100
    assert admin_values["properties"]["loginLockoutDuration"]["minimum"] == 60
    admin_field_items = _resolve_schema_ref(schema, admin_config["properties"]["fields"]["items"])
    assert admin_field_items["properties"]["key"]["maxLength"] == 64
    assert _string_schema(admin_field_items["properties"]["description"])["maxLength"] == 512

    admin_status = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/system/admin/status", "get")
    )
    assert admin_status["properties"]["timestamp"]["maxLength"] == 64
    admin_host = _resolve_schema_ref(schema, admin_status["properties"]["host"])
    assert admin_host["properties"]["cpu_count"]["maximum"] == 4096
    admin_metrics = _resolve_schema_ref(schema, admin_status["properties"]["metrics"])
    admin_disk = _resolve_schema_ref(schema, admin_metrics["properties"]["disk"])
    assert admin_disk["properties"]["total_bytes"]["anyOf"][0]["maximum"] == 9_000_000_000_000_000

    admin_health = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/system/admin/health", "get")
    )
    assert admin_health["properties"]["selenium"]["type"] == "boolean"
    admin_health_component = _resolve_schema_ref(
        schema, admin_health["properties"]["components"]["additionalProperties"]
    )
    assert admin_health_component["properties"]["latency_ms"]["maximum"] == 3_600_000

    gemini_pool_stats = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/system/admin/gemini-pool/stats", "get")
    )
    assert gemini_pool_stats["properties"]["hit_rate"]["maximum"] == 1
    assert gemini_pool_stats["properties"]["total_requests"]["maximum"] == 10_000_000_000
    gemini_pool_client = _resolve_schema_ref(
        schema, gemini_pool_stats["properties"]["clients"]["additionalProperties"]
    )
    assert gemini_pool_client["properties"]["api_key_configured"]["type"] == "boolean"

    admin_cleanup = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/system/admin/cleanup", "post")
    )
    assert admin_cleanup["properties"]["freed_bytes"]["maximum"] == 9_000_000_000_000_000
    assert admin_cleanup["properties"]["cleaned"]["additionalProperties"]["type"] == "integer"

    profiles_list = _response_schema(schema, "/api/profiles", "get")
    assert profiles_list["type"] == "array"
    assert profiles_list["maxItems"] == 10_000
    config_profile = _resolve_schema_ref(schema, profiles_list["items"])
    assert config_profile["properties"]["id"]["maxLength"] == 256
    assert config_profile["properties"]["api_key"]["maxLength"] == 4096
    assert config_profile["properties"]["hidden_models"]["maxItems"] == 512
    assert config_profile["properties"]["saved_models"]["maxItems"] == 512
    assert config_profile["properties"]["created_at"]["maximum"] == 4_102_444_800_000

    profile_upsert = _resolve_schema_ref(schema, _response_schema(schema, "/api/profiles", "post"))
    assert profile_upsert == config_profile

    full_settings = _resolve_schema_ref(schema, _response_schema(schema, "/api/settings/full", "get"))
    assert full_settings["properties"]["profiles"]["maxItems"] == 10_000
    assert _string_schema(full_settings["properties"]["active_profile_id"])["maxLength"] == 256
    assert full_settings["properties"]["dashscope_key"]["maxLength"] == 4096

    active_profile = _resolve_schema_ref(schema, _response_schema(schema, "/api/active-profile", "get"))
    assert _string_schema(active_profile["properties"]["id"])["maxLength"] == 256

    set_active_profile = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/active-profile", "post")
    )
    assert set_active_profile["properties"]["success"]["type"] == "boolean"
    assert _string_schema(set_active_profile["properties"]["id"])["maxLength"] == 256

    delete_profile = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/profiles/{profile_id}", "delete")
    )
    assert delete_profile["properties"]["success"]["type"] == "boolean"

    pdf_templates = _resolve_schema_ref(schema, _response_schema(schema, "/api/pdf/templates", "get"))
    assert pdf_templates["properties"]["templates"]["maxItems"] == 32
    pdf_template = _resolve_schema_ref(schema, pdf_templates["properties"]["templates"]["items"])
    assert pdf_template["properties"]["id"]["maxLength"] == 64
    assert pdf_template["properties"]["description"]["maxLength"] == 1024

    web_search = _resolve_schema_ref(schema, _response_schema(schema, "/api/search", "post"))
    assert web_search["properties"]["results"]["$ref"] == "#/components/schemas/JsonValue"

    pdf_extract = _response_schema(schema, "/api/pdf/extract", "post")
    assert pdf_extract["type"] == "object"
    assert pdf_extract["maxProperties"] == 256
    assert pdf_extract["additionalProperties"]["$ref"] == "#/components/schemas/JsonValue"

    dashscope_upload = _response_schema(schema, "/api/dashscope/api/v1/files", "post")
    assert dashscope_upload["type"] == "object"
    assert dashscope_upload["maxProperties"] == 256
    assert dashscope_upload["additionalProperties"]["$ref"] == "#/components/schemas/JsonValue"

    for method in ("get", "post", "put", "delete", "patch"):
        dashscope_content = schema["paths"]["/api/dashscope/{path}"][method]["responses"]["200"][
            "content"
        ]
        assert set(dashscope_content) == {"application/json", "text/event-stream"}
        dashscope_proxy = dashscope_content["application/json"]["schema"]
        assert dashscope_proxy["type"] == "object"
        assert dashscope_proxy["maxProperties"] == 256
        assert dashscope_proxy["additionalProperties"]["$ref"] == "#/components/schemas/JsonValue"
        assert dashscope_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    personas_save = _resolve_schema_ref(schema, _response_schema(schema, "/api/personas", "post"))
    assert personas_save["properties"]["success"]["type"] == "boolean"
    assert personas_save["properties"]["count"]["maximum"] == 10_000

    research_cancel = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/research/cancel/{interaction_id}", "post")
    )
    assert research_cancel["properties"]["message"]["maxLength"] == 128

    vertex_update = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/vertex-ai/config", "post")
    )
    assert vertex_update["properties"]["message"]["maxLength"] == 256
    vertex_config = _resolve_schema_ref(schema, vertex_update["properties"]["config"])
    assert vertex_config["properties"]["capabilities"]["maxProperties"] == 64
    assert vertex_config["properties"]["hidden_models"]["maxItems"] == 512
    assert vertex_config["properties"]["saved_models"]["maxItems"] == 512

    table_analysis = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/table/analysis", "post")
    )
    assert _resolve_schema_ref(
        schema, _response_schema(schema, "/api/table/analysis/inline", "post")
    ) == table_analysis
    assert table_analysis["properties"]["summary"]["maxProperties"] == 64
    assert table_analysis["properties"]["fields"]["maxItems"] == 10_000
    assert table_analysis["properties"]["numeric_summary"]["maxProperties"] == 10_000
    assert table_analysis["properties"]["sample_rows"]["maxItems"] == 100
    assert table_analysis["properties"]["evidence"]["maxProperties"] == 16

    table_export_content = schema["paths"]["/api/table/analysis/export"]["post"]["responses"]["200"][
        "content"
    ]
    assert set(table_export_content) == {"application/json", "text/markdown"}
    assert table_export_content["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TableAnalysisResponse"
    }
    assert table_export_content["text/markdown"]["schema"]["maxLength"] == 1_000_000

    ollama_params = schema["paths"]["/api/ollama/models"]["get"]["parameters"]
    assert ("api_key", "query") not in {
        (parameter["name"], parameter["in"]) for parameter in ollama_params
    }
    assert ("X-Ollama-Api-Key", "header") in {
        (parameter["name"], parameter["in"]) for parameter in ollama_params
    }

    ollama_models = _resolve_schema_ref(schema, _response_schema(schema, "/api/ollama/models", "get"))
    assert ollama_models["properties"]["models"]["maxItems"] == 10_000
    ollama_model = _resolve_schema_ref(schema, ollama_models["properties"]["models"]["items"])
    assert ollama_model["properties"]["name"]["maxLength"] == 256
    assert ollama_model["properties"]["size"]["maximum"] == 9_000_000_000_000_000
    ollama_details = _resolve_schema_ref(schema, ollama_model["properties"]["details"])
    assert ollama_details["properties"]["format"]["maxLength"] == 128

    ollama_info = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/ollama/models/{name}", "get")
    )
    assert ollama_info["properties"]["modelfile"]["maxLength"] == 1_000_000
    assert ollama_info["properties"]["model_info"]["maxProperties"] == 10_000
    assert ollama_info["properties"]["capabilities"]["maxItems"] == 64

    ollama_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/ollama/models/{name}", "delete")
    )
    assert ollama_delete["properties"]["message"]["maxLength"] == 512

    ollama_pull_content = schema["paths"]["/api/ollama/pull"]["post"]["responses"]["200"][
        "content"
    ]
    assert set(ollama_pull_content) == {"text/event-stream"}
    assert ollama_pull_content["text/event-stream"]["schema"]["maxLength"] == 1_000_000

    continuity = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/attachments/resolve-continuity", "post")
    )
    assert continuity["properties"]["attachment_id"]["maxLength"] == 512
    assert continuity["properties"]["url"]["anyOf"][0]["maxLength"] == 100_000_000
    assert continuity["properties"]["status"]["maxLength"] == 64
    assert continuity["properties"]["size"]["anyOf"][0]["maximum"] == 10_000_000_000
    assert continuity["properties"]["cloud_url"]["anyOf"][0]["maxLength"] == 100_000_000

    cloud_url = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/attachments/{attachment_id}/cloud-url", "get")
    )
    assert cloud_url["properties"]["url"]["anyOf"][0]["maxLength"] == 100_000_000
    assert cloud_url["properties"]["upload_status"]["maxLength"] == 64

    temp_image_content = schema["paths"]["/api/temp-images/{attachment_id}"]["get"]["responses"][
        "200"
    ]["content"]
    assert set(temp_image_content) == {
        "application/octet-stream",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
    }
    assert temp_image_content["image/png"]["schema"]["format"] == "binary"
    assert temp_image_content["image/png"]["schema"]["maxLength"] == 100_000_000

    batch_progress = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/batch-jobs/submit", "post")
    )
    for batch_path, batch_method in (
        ("/api/batch-jobs/{job_id}/progress", "get"),
        ("/api/batch-jobs/{job_id}/retry", "post"),
        ("/api/batch-jobs/{job_id}/resume", "post"),
        ("/api/batch-jobs/{job_id}/cancel", "post"),
    ):
        assert _resolve_schema_ref(schema, _response_schema(schema, batch_path, batch_method)) == batch_progress
    assert batch_progress["properties"]["job_id"]["maxLength"] == 128
    assert batch_progress["properties"]["progress_percent"]["maximum"] == 100
    assert batch_progress["properties"]["created_at"]["maximum"] == 4_102_444_800_000
    assert batch_progress["properties"]["items"]["maxItems"] == 10_000
    batch_counts = _resolve_schema_ref(schema, batch_progress["properties"]["counts"])
    assert batch_counts["properties"]["total"]["maximum"] == 10_000
    batch_item = _resolve_schema_ref(schema, batch_progress["properties"]["items"]["items"])
    assert batch_item["properties"]["item_id"]["maxLength"] == 512
    assert batch_item["properties"]["label"]["maxLength"] == 1_000_000
    assert batch_item["properties"]["attempts"]["maximum"] == 10_000

    batch_summary = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/batch-jobs/{job_id}/summary", "get")
    )
    assert batch_summary["properties"]["failed_item_ids"]["maxItems"] == 10_000
    assert batch_summary["properties"]["failed_item_ids"]["items"]["maxLength"] == 512
    assert batch_summary["properties"]["completed_items"]["maxItems"] == 10_000
    batch_table_metrics = _resolve_schema_ref(schema, batch_summary["properties"]["table_metrics"])
    assert batch_table_metrics["properties"]["total_rows"]["maximum"] == 1_000_000_000
    batch_completed_item = _resolve_schema_ref(
        schema, batch_summary["properties"]["completed_items"]["items"]
    )
    assert batch_completed_item["properties"]["summary"]["$ref"] == "#/components/schemas/JsonValue"

    mcp_config = _resolve_schema_ref(schema, _response_schema(schema, "/api/mcp/config", "get"))
    assert mcp_config["properties"]["config_json"]["maxLength"] == 10_000_000
    assert mcp_config["properties"]["updated_at"]["anyOf"][0]["format"] == "date-time"

    mcp_config_update = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/mcp/config", "put")
    )
    assert mcp_config_update == mcp_config

    mcp_tools = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/mcp/config/tools/{server_key}", "get")
    )
    assert mcp_tools["properties"]["server_key"]["maxLength"] == 512
    assert mcp_tools["properties"]["tool_count"]["maximum"] == 10_000
    assert mcp_tools["properties"]["tools"]["maxItems"] == 10_000
    mcp_tool = _resolve_schema_ref(schema, mcp_tools["properties"]["tools"]["items"])
    assert mcp_tool["properties"]["name"]["maxLength"] == 512
    assert mcp_tool["properties"]["description"]["maxLength"] == 100_000

    mcp_invoke = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/mcp/config/tools/{server_key}/invoke", "post")
    )
    assert mcp_invoke["properties"]["tool_name"]["maxLength"] == 512
    assert mcp_invoke["properties"]["latency_ms"]["maximum"] == 3_600_000
    assert mcp_invoke["properties"]["timestamp"]["maximum"] == 4_102_444_800
    assert mcp_invoke["properties"]["success"]["type"] == "boolean"
    assert mcp_invoke["properties"]["is_error"]["type"] == "boolean"
    assert any(
        branch.get("$ref") == "#/components/schemas/JsonValue"
        for branch in mcp_invoke["properties"]["result"]["anyOf"]
    )

    mcp_stop = _resolve_schema_ref(schema, _response_schema(schema, "/api/mcp/session/stop", "post"))
    assert mcp_stop["properties"]["closed_count"]["maximum"] == 10_000
    assert mcp_stop["properties"]["closed_sessions"]["maxItems"] == 10_000
    assert mcp_stop["properties"]["closed_sessions"]["items"]["maxLength"] == 512

    workflow_pause = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/history/{execution_id}/pause", "post")
    )
    assert workflow_pause["properties"]["execution_id"]["maxLength"] == 256
    assert workflow_pause["properties"]["status"]["maxLength"] == 32
    pause_requested_type = workflow_pause["properties"]["pause_requested"]["type"]
    assert pause_requested_type == "boolean" or (
        isinstance(pause_requested_type, list) and "boolean" in pause_requested_type
    )
    checkpoint = _resolve_schema_ref(
        schema,
        next(
            branch
            for branch in workflow_pause["properties"]["checkpoint"]["anyOf"]
            if "$ref" in branch
        ),
    )
    assert checkpoint["properties"]["captured_at"]["maximum"] == 4_102_444_800_000
    runtime_metrics = _resolve_schema_ref(
        schema,
        next(
            branch
            for branch in workflow_pause["properties"]["runtime_metrics"]["anyOf"]
            if "$ref" in branch
        ),
    )
    assert runtime_metrics["properties"]["subscriber_count"]["maximum"] == 1_000_000

    workflow_resume = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/history/{execution_id}/resume", "post")
    )
    assert _string_schema(workflow_resume["properties"]["resume_strategy"])["maxLength"] == 32

    workflow_cancel = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/history/{execution_id}/cancel", "post")
    )
    cancel_transitioned_type = workflow_cancel["properties"]["cancel_transitioned"]["type"]
    assert cancel_transitioned_type == "boolean" or (
        isinstance(cancel_transitioned_type, list) and "boolean" in cancel_transitioned_type
    )

    agent_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/agents/{agent_id}", "delete")
    )
    assert agent_delete["properties"]["success"]["type"] == "boolean"
    assert agent_delete["properties"]["deleted_mode"]["maxLength"] == 16

    agent_create = _resolve_schema_ref(schema, _response_schema(schema, "/api/agents", "post"))
    assert agent_create["properties"]["id"]["maxLength"] == 256
    assert agent_create["properties"]["name"]["maxLength"] == 128
    assert agent_create["properties"]["system_prompt"]["maxLength"] == 100_000
    assert agent_create["properties"]["created_at"]["maximum"] == 4_102_444_800_000
    assert agent_create["properties"]["supports_runtime_sessions"]["type"] == "boolean"
    agent_runtime = _resolve_schema_ref(schema, agent_create["properties"]["runtime"])
    assert agent_runtime["properties"]["supports_official_orchestration"]["type"] == "boolean"
    agent_source = _resolve_schema_ref(schema, agent_create["properties"]["source"])
    assert agent_source["properties"]["is_system"]["type"] == "boolean"

    agent_list = _resolve_schema_ref(schema, _response_schema(schema, "/api/agents", "get"))
    assert agent_list["properties"]["agents"]["maxItems"] == 10_000
    assert agent_list["properties"]["active_count"]["maximum"] == 10_000
    task_counts = _resolve_schema_ref(schema, agent_list["properties"]["task_counts"])
    assert task_counts["additionalProperties"]["type"] == "integer"
    listed_agent = _resolve_schema_ref(schema, agent_list["properties"]["agents"]["items"])
    assert listed_agent["properties"]["model_id"]["anyOf"][0]["maxLength"] == 256

    agent_detail = _resolve_schema_ref(schema, _response_schema(schema, "/api/agents/{agent_id}", "get"))
    assert agent_detail["properties"]["status"]["maxLength"] == 32

    agent_update = _resolve_schema_ref(schema, _response_schema(schema, "/api/agents/{agent_id}", "put"))
    assert agent_update["properties"]["temperature"]["anyOf"][0]["maximum"] == 2

    agent_restore = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/agents/{agent_id}/restore", "post")
    )
    assert agent_restore["properties"]["success"]["type"] == "boolean"
    restored_agent = _resolve_schema_ref(schema, agent_restore["properties"]["agent"])
    assert restored_agent["properties"]["updated_at"]["maximum"] == 4_102_444_800_000

    available_models = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/agents/available-models", "get")
    )
    assert available_models["properties"]["providers"]["maxItems"] == 10_000
    provider_models = _resolve_schema_ref(schema, available_models["properties"]["providers"]["items"])
    assert provider_models["properties"]["all_models"]["maxItems"] == 1_000
    model_item = _resolve_schema_ref(schema, provider_models["properties"]["all_models"]["items"])
    assert model_item["properties"]["id"]["maxLength"] == 256
    assert model_item["properties"]["supported_tasks"]["maxItems"] == 16
    selection_policy = _resolve_schema_ref(schema, available_models["properties"]["selection_policy"])
    assert selection_policy["properties"]["tasks"]["maxItems"] == 16

    template_delete = _resolve_schema_ref(
        schema, _response_schema(schema, "/api/workflows/templates/{template_id}", "delete")
    )
    assert template_delete["properties"]["success"]["type"] == "boolean"
