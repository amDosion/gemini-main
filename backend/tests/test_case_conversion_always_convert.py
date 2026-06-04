"""always_convert_response: app-owned large endpoints stay camelCase past 2 MiB.

The middleware passes responses larger than MAX_RESPONSE_CONVERSION_BYTES through
UNCONVERTED (snake_case) as a memory safety valve. For app-owned unpaginated
endpoints (/sessions, /api/agents, /api/agents/available-models) that can exceed
the threshold, that means the frontend would receive snake_case and break.

case_conversion_options(always_convert_response=True) opts an endpoint out of the
oversized passthrough so it is ALWAYS converted -> the frontend never converts.
"""

import logging

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.middleware import case_conversion_middleware as ccm
from app.middleware.case_conversion_middleware import (
    CaseConversionMiddleware,
    CaseConversionOptions,
    case_conversion_options,
)


def _make_app():
    app = FastAPI()
    app.add_middleware(CaseConversionMiddleware)

    @app.get("/big-default")
    async def big_default():
        return {"some_snake_key": "x" * 200, "another_key": 1}

    @app.get("/big-forced")
    @case_conversion_options(always_convert_response=True)
    async def big_forced():
        return {"some_snake_key": "x" * 200, "another_key": 1}

    # Mirror the real ADK pattern: TWO stacked route decorators (primary + legacy
    # alias) over a single @case_conversion_options-decorated handler. Proves the
    # option survives decorator stacking and is honored at RUNTIME on every route,
    # not merely readable via from_endpoint on the bare function.
    @app.get("/stacked/primary")
    @app.get("/stacked/legacy")
    @case_conversion_options(always_convert_response=True)
    async def big_forced_stacked():
        return {"some_snake_key": "x" * 200, "another_key": 1}

    return app


def test_undecodable_json_response_passes_through_and_logs(caplog):
    # A response declared application/json whose body is not decodable JSON must be
    # passed through UNCHANGED (converting is impossible) but the skip must be LOGGED
    # so the silent path is observable instead of invisible (no swallowed failures).
    app = FastAPI()
    app.add_middleware(CaseConversionMiddleware)

    bad = b"{not valid json"  # valid utf-8, invalid JSON -> JSONDecodeError

    @app.get("/bad-json")
    async def bad_json():
        return Response(content=bad, media_type="application/json")

    client = TestClient(app)
    with caplog.at_level(logging.WARNING, logger="app.middleware.case_conversion_middleware"):
        resp = client.get("/bad-json")

    assert resp.content == bad  # body untouched, not corrupted
    assert any(
        "Skipped response conversion" in r.getMessage() for r in caplog.records
    ), "undecodable JSON body should log a warning, not be skipped silently"


def test_default_endpoint_passes_through_oversized_as_snake(monkeypatch):
    monkeypatch.setattr(ccm, "MAX_RESPONSE_CONVERSION_BYTES", 50)
    client = TestClient(_make_app())
    data = client.get("/big-default").json()
    # > threshold and not opted-in -> passthrough -> stays snake_case
    assert "some_snake_key" in data
    assert "someSnakeKey" not in data


def test_forced_endpoint_converts_even_when_oversized(monkeypatch):
    monkeypatch.setattr(ccm, "MAX_RESPONSE_CONVERSION_BYTES", 50)
    client = TestClient(_make_app())
    data = client.get("/big-forced").json()
    # > threshold but opted-in -> still converted -> camelCase
    assert "someSnakeKey" in data
    assert "some_snake_key" not in data


def test_forced_endpoint_still_converts_when_small(monkeypatch):
    # below threshold: normal conversion path, must also be camelCase
    client = TestClient(_make_app())
    data = client.get("/big-forced").json()
    assert "someSnakeKey" in data


@pytest.mark.parametrize("path", ["/stacked/primary", "/stacked/legacy"])
def test_stacked_route_decorators_still_force_conversion(monkeypatch, path):
    # The ADK endpoints stack two @router.get over one @case_conversion_options
    # handler. Both routes must honor always_convert_response past the threshold.
    monkeypatch.setattr(ccm, "MAX_RESPONSE_CONVERSION_BYTES", 50)
    client = TestClient(_make_app())
    data = client.get(path).json()
    assert "someSnakeKey" in data
    assert "some_snake_key" not in data


# --- Regression guard: the real app-owned endpoints MUST carry the flag ---------
# The frontend now reads camelCase ONLY (snake fallbacks removed), so these
# unpaginated app-owned endpoints must stay opted into always_convert_response.
# If someone drops the decorator, the >2 MiB snake passthrough bug silently
# returns -- these tests fail loudly instead.


def test_sessions_endpoints_opt_into_always_convert():
    from app.routers.user import sessions

    assert CaseConversionOptions.from_endpoint(sessions.get_sessions).always_convert_response
    assert CaseConversionOptions.from_endpoint(sessions.get_session).always_convert_response


def test_agents_endpoints_opt_into_always_convert():
    from app.routers.ai import workflows

    assert CaseConversionOptions.from_endpoint(workflows.list_agents).always_convert_response
    assert CaseConversionOptions.from_endpoint(
        workflows.get_available_models_for_agents
    ).always_convert_response


def test_adk_runtime_session_endpoints_opt_into_always_convert():
    # ADK runtime session list + snapshot are app-owned and unpaginated; the
    # frontend (adkSessionApi/AdkSessionPanel) now reads sessionId/updatedAt/
    # lastUpdateTime only, so a >2 MiB snapshot must not pass through as snake.
    from app.routers.ai import multi_agent

    assert CaseConversionOptions.from_endpoint(
        multi_agent.list_adk_agent_sessions
    ).always_convert_response
    assert CaseConversionOptions.from_endpoint(
        multi_agent.get_adk_agent_session
    ).always_convert_response


def test_mcp_config_endpoints_opt_into_always_convert():
    # MCP config is a user-controlled JSON blob in a Text column with no size cap;
    # the frontend (mcpConfigService) reads configJson/updatedAt only, so a large
    # saved config must stay camelCase instead of loading as null.
    from app.routers.user import mcp_config

    assert CaseConversionOptions.from_endpoint(mcp_config.get_mcp_config).always_convert_response
    assert CaseConversionOptions.from_endpoint(
        mcp_config.update_mcp_config
    ).always_convert_response


def test_mcp_tool_endpoints_opt_into_always_convert():
    # The whole mcpConfigService-consumed surface reads camelCase only
    # (serverKey/toolCount/tools, serverKey/toolName/sessionId/latencyMs). The tools
    # list is unbounded and invoke spreads **result.to_dict() (unbounded tool
    # output), so they must stay camelCase past 2 MiB. stop is small but marked too
    # to keep the MCP service surface one uniform conversion contract.
    from app.routers.user import mcp_config

    assert CaseConversionOptions.from_endpoint(
        mcp_config.get_mcp_server_tools
    ).always_convert_response
    assert CaseConversionOptions.from_endpoint(
        mcp_config.invoke_mcp_server_tool
    ).always_convert_response
    assert CaseConversionOptions.from_endpoint(
        mcp_config.stop_mcp_sessions
    ).always_convert_response


def test_workflow_history_detail_opts_into_always_convert():
    # GET /api/workflows/history/{id} returns an UNPAGINATED detail (full result +
    # node executions + media) that can exceed 2 MiB. buildExecutionStatusFromHistoryDetail
    # reads payload.nodeExecutions/nodeStatuses/nodeResults/resultSummary camelCase
    # only, so a snake passthrough would render the restored history detail blank.
    # (The /history LIST endpoint is server-side capped at 100 -> bounded -> not marked.)
    from app.routers.ai import workflows

    assert CaseConversionOptions.from_endpoint(
        workflows.get_workflow_history_detail
    ).always_convert_response


def test_workflow_templates_list_opts_into_always_convert():
    # GET /api/workflows/templates is UNPAGINATED and each template carries a full
    # node/edge graph, so the response can exceed 2 MiB. migrateTemplate reads
    # top-level template fields (estimatedNodeCount, id, workflowType, nodes...)
    # camelCase only, so a snake passthrough would break template rendering.
    # (template-categories is a small name list -> bounded -> not marked.)
    from app.routers.ai import workflows

    assert CaseConversionOptions.from_endpoint(
        workflows.list_workflow_templates
    ).always_convert_response


def test_workflow_template_single_object_endpoints_opt_into_always_convert():
    # Every endpoint returning a full WorkflowTemplate object is read camelCase only
    # by the frontend (migrateTemplate / normalizeTemplateResponse read
    # workflowType/userId/createdAt/config.* with no snake fallback). A single large
    # template graph can exceed 2 MiB, so the whole template surface must be uniform:
    # GET detail (future-proofed; no consumer yet), copy, create, update.
    from app.routers.ai import workflows

    for fn in (
        workflows.get_workflow_template,
        workflows.copy_workflow_template,
        workflows.create_workflow_template,
        workflows.update_workflow_template,
    ):
        assert CaseConversionOptions.from_endpoint(fn).always_convert_response, fn.__name__


def test_profiles_list_opts_into_always_convert():
    # GET /api/profiles returns the user's full UNPAGINATED config-profile list; each
    # profile's saved_models can hold a whole provider catalog. db.getProfiles reads
    # ConfigProfile (providerId/apiKey/baseUrl/isProxy/hiddenModels/createdAt) camelCase
    # only (Profile.to_dict() emits snake), so a large profile set must stay camelCase.
    from app.routers.user import profiles

    assert CaseConversionOptions.from_endpoint(profiles.get_profiles).always_convert_response


def test_available_models_opts_into_always_convert():
    # GET /api/models/{provider} returns an UNPAGINATED model catalog (OpenRouter etc.
    # carry hundreds of models). ModelsApiResponse reads models/defaultModelId/
    # modeCatalog/filteredByMode camelCase only, so a large catalog must stay camelCase.
    from app.routers.models import models

    assert CaseConversionOptions.from_endpoint(models.get_available_models).always_convert_response


def test_full_settings_opts_into_always_convert():
    # GET /api/settings/full returns ALL profiles (to_dict snake, unbounded saved_models)
    # plus active profile + settings; configurationService reads FullSettings camelCase
    # only, so a large profile set must stay camelCase.
    from app.routers.user import profiles

    assert CaseConversionOptions.from_endpoint(profiles.get_full_settings).always_convert_response


def test_session_history_states_opts_into_always_convert():
    # GET /sessions/{id}/history-states returns ALL MessageHistoryState rows for a
    # session with no limit; db.getSessionHistoryStates reads SessionHistoryState[]
    # camelCase only, so an edit-heavy session must stay camelCase.
    from app.routers.user import sessions

    assert CaseConversionOptions.from_endpoint(
        sessions.get_session_history_states
    ).always_convert_response


def test_storage_configs_opts_into_always_convert():
    # GET /api/storage/configs returns the user's full UNPAGINATED storage-config list
    # (credentials/config blobs); db.getStorageConfigs reads StorageConfig[] camelCase
    # only (createdAt/...), so a large config set must stay camelCase.
    from app.routers.storage import storage

    assert CaseConversionOptions.from_endpoint(storage.get_storage_configs).always_convert_response


def test_storage_browse_and_batch_opts_into_always_convert():
    # Browse pages are limit<=1000 with rich per-item metadata (previewUrl etc.), so a
    # single PAGE can exceed 2 MiB despite pagination; batch-delete returns a per-item
    # results list bounded only by the (user-controlled) request size. CloudStorageView
    # / db.browseStorage read StorageBrowseResponse (storageId/entryType/previewUrl/
    # nextCursor) and the batch result (successCount/...) camelCase only.
    from app.routers.storage import storage

    for fn in (
        storage.browse_active_storage,
        storage.browse_storage,
        storage.batch_delete_storage_items,
    ):
        assert CaseConversionOptions.from_endpoint(fn).always_convert_response, fn.__name__


def test_init_endpoints_opt_into_always_convert():
    # The bootstrap endpoints return composite app data — profiles (to_dict snake,
    # with unbounded saved_models) + storage configs + personas + first-message
    # sessions — consumed camelCase only by useInitData. A large account must not get
    # the whole app init in snake_case past the 2 MiB valve. /init/sessions/more stays
    # paginated (not marked).
    from app.routers.user import init

    for fn in (
        init.get_critical_init_data,
        init.get_non_critical_init_data,
        init.get_init,
    ):
        assert CaseConversionOptions.from_endpoint(fn).always_convert_response, fn.__name__


def test_personas_list_opts_into_always_convert():
    # GET /personas returns the user's full UNPAGINATED persona list; each persona's
    # system_prompt (-> systemPrompt) can be long. db.getPersonas reads Persona[]
    # with systemPrompt camelCase only (Persona.to_dict() emits snake), so a large
    # persona set must stay camelCase instead of losing every system prompt.
    from app.routers.user import personas

    assert CaseConversionOptions.from_endpoint(personas.get_personas).always_convert_response
