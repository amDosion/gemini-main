"""
WorkflowEngine - 工作流执行引擎 (Phase 3)

支持节点类型：
- start / end / agent
- condition / router / parallel / merge / loop / human / tool
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from ..agent_llm_service import AgentLLMService
from ..execution_context import ExecutionContext
from .builtin_tools import (
    build_sheet_stage_request_payload as workflow_build_sheet_stage_request_payload,
    execute_builtin_tool as workflow_execute_builtin_tool,
    extract_mcp_server_map as workflow_extract_mcp_server_map,
    extract_sheet_stage_artifact_ref_from_value as workflow_extract_sheet_stage_artifact_ref_from_value,
    extract_sheet_stage_session_id_from_value as workflow_extract_sheet_stage_session_id_from_value,
    fetch_duckduckgo_results as workflow_fetch_duckduckgo_results,
    get_sheet_stage_artifact_service as workflow_get_sheet_stage_artifact_service,
    load_workflow_mcp_server_config as workflow_load_workflow_mcp_server_config,
    normalize_mcp_args_list as workflow_normalize_mcp_args_list,
    normalize_mcp_env_map as workflow_normalize_mcp_env_map,
    normalize_search_items as workflow_normalize_search_items,
    run_mcp_tool_call as workflow_run_mcp_tool_call,
    run_read_webpage_tool as workflow_run_read_webpage_tool,
    run_selenium_browse_tool as workflow_run_selenium_browse_tool,
    run_sheet_stage_tool as workflow_run_sheet_stage_tool,
    run_web_search_tool as workflow_run_web_search_tool,
)
from .amazon_ads import (
    build_amazon_ads_decision_board as workflow_build_amazon_ads_decision_board,
    build_amazon_ads_validation_summary as workflow_build_amazon_ads_validation_summary,
    format_money as workflow_format_money,
    format_ratio as workflow_format_ratio,
    match_amazon_ads_columns as workflow_match_amazon_ads_columns,
    normalize_header_token as workflow_normalize_header_token,
    normalize_text_value as workflow_normalize_text_value,
    parse_boolean_value as workflow_parse_boolean_value,
    parse_numeric_value as workflow_parse_numeric_value,
    parse_ratio_value as workflow_parse_ratio_value,
    resolve_column_by_alias as workflow_resolve_column_by_alias,
    run_amazon_ads_keyword_optimize_tool as workflow_run_amazon_ads_keyword_optimize_tool,
    safe_ratio as workflow_safe_ratio,
)
from .agent_resolution import (
    build_inline_agent as workflow_build_inline_agent,
    create_provider_service as workflow_create_provider_service,
    create_tool_provider_service as workflow_create_tool_provider_service,
    default_text_model_for_provider as workflow_default_text_model_for_provider,
    extract_agent_card_defaults as workflow_extract_agent_card_defaults,
    extract_agent_llm_defaults as workflow_extract_agent_llm_defaults,
    extract_model_version as workflow_extract_model_version,
    generate_workflow_frontend_session_id as workflow_generate_workflow_frontend_session_id,
    get_default_audio_model as workflow_get_default_audio_model,
    get_default_image_model as workflow_get_default_image_model,
    get_default_video_model as workflow_get_default_video_model,
    get_user_profiles as workflow_get_user_profiles,
    get_workflow_user_id as workflow_get_workflow_user_id,
    invoke_llm_chat as workflow_invoke_llm_chat,
    is_active_inline_provider_token as workflow_is_active_inline_provider_token,
    is_auto_inline_model_token as workflow_is_auto_inline_model_token,
    is_candidate_for_agent_task as workflow_is_candidate_for_agent_task,
    is_usable_requested_image_model as workflow_is_usable_requested_image_model,
    list_candidate_image_models as workflow_list_candidate_image_models,
    list_saved_model_ids as workflow_list_saved_model_ids,
    looks_like_audio_generation_model as workflow_looks_like_audio_generation_model,
    looks_like_google_chat_image_edit_model as workflow_looks_like_google_chat_image_edit_model,
    looks_like_image_edit_model as workflow_looks_like_image_edit_model,
    looks_like_image_generation_model as workflow_looks_like_image_generation_model,
    looks_like_text_model as workflow_looks_like_text_model,
    looks_like_video_generation_model as workflow_looks_like_video_generation_model,
    looks_like_vision_understand_model as workflow_looks_like_vision_understand_model,
    rank_model_for_agent_task as workflow_rank_model_for_agent_task,
    rank_provider_profiles_for_tool as workflow_rank_provider_profiles_for_tool,
    resolve_image_model_for_profile as workflow_resolve_image_model_for_profile,
    resolve_llm_default_value as workflow_resolve_llm_default_value,
    resolve_preferred_model_for_agent_task as workflow_resolve_preferred_model_for_agent_task,
    run_adk_text_chat as workflow_run_adk_text_chat,
    select_image_model as workflow_select_image_model,
    select_profile_target_for_agent_task as workflow_select_profile_target_for_agent_task,
    select_provider_profile_for_tool as workflow_select_provider_profile_for_tool,
    select_text_chat_target as workflow_select_text_chat_target,
    should_resolve_inline_from_active_profile as workflow_should_resolve_inline_from_active_profile,
    should_use_adk_runtime as workflow_should_use_adk_runtime,
)
from .flow_control import (
    derive_node_input_text as workflow_derive_node_input_text,
    evaluate_contains_clause as workflow_evaluate_contains_clause,
    evaluate_contains_expression as workflow_evaluate_contains_expression,
    evaluate_expression as workflow_evaluate_expression,
    get_node_type as workflow_get_node_type,
    get_source_handle as workflow_get_source_handle,
    merge_outputs as workflow_merge_outputs,
    parse_tool_args as workflow_parse_tool_args,
    resolve_max_parallel_nodes as workflow_resolve_max_parallel_nodes,
    resolve_max_visits as workflow_resolve_max_visits,
    resolve_template_value as workflow_resolve_template_value,
    resolve_tool_args_template as workflow_resolve_tool_args_template,
    select_outgoing_edges as workflow_select_outgoing_edges,
    select_router_branch as workflow_select_router_branch,
    select_router_branch_heuristic as workflow_select_router_branch_heuristic,
)
from .image_pipeline import (
    build_generate_kwargs as workflow_build_generate_kwargs,
    build_guarded_edit_prompt as workflow_build_guarded_edit_prompt,
    build_image_edit_kwargs as workflow_build_image_edit_kwargs,
    build_vision_understand_prompt as workflow_build_vision_understand_prompt,
    build_vision_understand_summary as workflow_build_vision_understand_summary,
    extract_json_object_from_text as workflow_extract_json_object_from_text,
    guess_audio_mime_type as workflow_guess_audio_mime_type,
    normalize_resolution_tier as workflow_normalize_resolution_tier,
    resolve_generic_image_size as workflow_resolve_generic_image_size,
    resolve_google_image_size as workflow_resolve_google_image_size,
    resolve_tongyi_resolution as workflow_resolve_tongyi_resolution,
    resolve_video_resolution as workflow_resolve_video_resolution,
    run_image_edit_tool as workflow_run_image_edit_tool,
    run_image_generate_tool as workflow_run_image_generate_tool,
    run_vision_understand_task as workflow_run_vision_understand_task,
    sanitize_vision_text_prompt as workflow_sanitize_vision_text_prompt,
    select_google_vision_eval_model as workflow_select_google_vision_eval_model,
    validate_image_edit_result as workflow_validate_image_edit_result,
)
from .orchestration import (
    emit_callback as workflow_emit_callback,
    execute as workflow_execute,
    execute_node as workflow_execute_node,
    record_trace_event as workflow_record_trace_event,
    resolve_agent_timeout_seconds as workflow_resolve_agent_timeout_seconds,
)
from .media import (
    build_audio_generate_kwargs as workflow_build_audio_generate_kwargs,
    build_video_generate_kwargs as workflow_build_video_generate_kwargs,
    is_outpaint_mode_token as workflow_is_outpaint_mode_token,
    normalize_audio_service_result as workflow_normalize_audio_service_result,
    normalize_image_edit_mode as workflow_normalize_image_edit_mode,
    normalize_image_service_results as workflow_normalize_image_service_results,
    normalize_mode_token_for_routing as workflow_normalize_mode_token_for_routing,
    normalize_video_service_result as workflow_normalize_video_service_result,
    resolve_image_tool_route as workflow_resolve_image_tool_route,
    run_audio_generate_task as workflow_run_audio_generate_task,
    run_video_delete_task as workflow_run_video_delete_task,
    run_video_generate_task as workflow_run_video_generate_task,
    run_video_understand_task as workflow_run_video_understand_task,
    trim_normalized_images as workflow_trim_normalized_images,
)
from .analysis_tools import (
    run_prompt_optimize_tool as workflow_run_prompt_optimize_tool,
    run_sheet_analyze_tool as workflow_run_sheet_analyze_tool,
    run_table_analyze_tool as workflow_run_table_analyze_tool,
)
from .agent_execution import (
    execute_agent_node as workflow_execute_agent_node,
)
from .payload_media import (
    build_source_video_payload as workflow_build_source_video_payload,
    extract_all_image_urls as workflow_extract_all_image_urls,
    extract_first_image_url as workflow_extract_first_image_url,
    extract_first_video_url as workflow_extract_first_video_url,
    extract_result_image_urls as workflow_extract_result_image_urls,
    get_tool_arg as workflow_get_tool_arg,
    guess_image_mime_type_from_reference as workflow_guess_image_mime_type_from_reference,
    is_disallowed_reference_hostname as workflow_is_disallowed_reference_hostname,
    is_disallowed_reference_ip as workflow_is_disallowed_reference_ip,
    looks_like_excel_binary as workflow_looks_like_excel_binary,
    normalize_possible_file_url as workflow_normalize_possible_file_url,
    normalize_possible_image_url as workflow_normalize_possible_image_url,
    normalize_possible_result_media_url as workflow_normalize_possible_result_media_url,
    normalize_reference_image_for_provider as workflow_normalize_reference_image_for_provider,
    parse_reference_ip_host as workflow_parse_reference_ip_host,
    resolve_agent_reference_image_url as workflow_resolve_agent_reference_image_url,
    resolve_agent_source_video_input as workflow_resolve_agent_source_video_input,
    resolve_agent_source_video_url as workflow_resolve_agent_source_video_url,
    resolve_generic_path as workflow_resolve_generic_path,
    to_bool as workflow_to_bool,
)
from .references import (
    build_file_reference_context as workflow_build_file_reference_context,
    bytes_to_dataframe as workflow_bytes_to_dataframe,
    load_binary_from_reference as workflow_load_binary_from_reference,
    normalize_dataframe as workflow_normalize_dataframe,
    table_payload_to_dataframe as workflow_table_payload_to_dataframe,
    table_payload_to_text as workflow_table_payload_to_text,
    text_to_dataframe as workflow_text_to_dataframe,
    validate_remote_reference_url as workflow_validate_remote_reference_url,
)
from .text_utils import (
    build_node_input_snapshot as workflow_build_node_input_snapshot,
    build_text_preview as workflow_build_text_preview,
    decode_bytes_to_text as workflow_decode_bytes_to_text,
    decode_data_url as workflow_decode_data_url,
    dict_rows_to_csv as workflow_dict_rows_to_csv,
    extract_text_from_value as workflow_extract_text_from_value,
    normalize_agent_response_text as workflow_normalize_agent_response_text,
    strip_markdown_code_fence as workflow_strip_markdown_code_fence,
    to_float as workflow_to_float,
    to_int as workflow_to_int,
    truncate_text as workflow_truncate_text,
)
from ....core.config import settings

logger = logging.getLogger(__name__)

ACTIVE_INLINE_PROVIDER_TOKENS = {
    "__active__",
    "__current__",
    "active",
    "current",
    "active-profile",
    "current-profile",
}
AUTO_INLINE_MODEL_TOKENS = {
    "",
    "__auto__",
    "__active__",
    "auto",
    "active",
    "current",
    "active-profile",
    "current-profile",
}

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pd = None  # type: ignore


class WorkflowEngine:
    """工作流执行引擎：支持动态分支与循环"""

    MAX_TOTAL_STEPS = 600
    DEFAULT_MAX_NODE_VISITS = 40
    DEFAULT_MAX_PARALLEL_NODES = 6
    DEFAULT_AGENT_TIMEOUT_SECONDS = 180
    DEFAULT_DATA_AGENT_TIMEOUT_SECONDS = 420
    DEFAULT_IMAGE_AGENT_TIMEOUT_SECONDS = 600
    DEFAULT_VIDEO_AGENT_TIMEOUT_SECONDS = 900
    REFERENCE_METADATA_HOSTS = {
        "metadata",
        "metadata.google.internal",
        "instance-data",
        "instance-data.ec2.internal",
    }
    REFERENCE_METADATA_IPS = {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("169.254.170.2"),
        ipaddress.ip_address("100.100.100.200"),
    }

    def __init__(
        self,
        db: Session,
        llm_service: AgentLLMService,
        callback_plugins: Optional[List[Any]] = None,
    ):
        self.db = db
        self.llm_service = llm_service
        self.callback_plugins = list(callback_plugins or [])
        # 执行期缓存：减少同一工作流内重复 DB 查询
        self._agent_cache_by_id: Dict[Tuple[str, str], Any] = {}
        self._agent_cache_by_name: Dict[Tuple[str, str], Any] = {}
        self._profiles_cache: Dict[str, List[Any]] = {}
        self._saved_model_ids_cache: Dict[str, List[str]] = {}
        self._trace_events: List[Dict[str, Any]] = []

    _resolve_max_visits = workflow_resolve_max_visits
    _resolve_max_parallel_nodes = workflow_resolve_max_parallel_nodes
    _select_outgoing_edges = workflow_select_outgoing_edges
    _get_source_handle = workflow_get_source_handle
    _get_node_type = workflow_get_node_type
    _derive_node_input_text = workflow_derive_node_input_text
    _build_node_input_snapshot = workflow_build_node_input_snapshot
    _extract_text_from_value = workflow_extract_text_from_value
    _strip_markdown_code_fence = workflow_strip_markdown_code_fence
    _normalize_agent_response_text = workflow_normalize_agent_response_text
    _evaluate_contains_clause = workflow_evaluate_contains_clause
    _evaluate_contains_expression = workflow_evaluate_contains_expression
    _evaluate_expression = workflow_evaluate_expression
    _select_router_branch = workflow_select_router_branch
    _select_router_branch_heuristic = workflow_select_router_branch_heuristic
    _merge_outputs = workflow_merge_outputs
    _parse_tool_args = workflow_parse_tool_args
    _resolve_tool_args_template = workflow_resolve_tool_args_template
    _resolve_template_value = workflow_resolve_template_value
    _to_int = workflow_to_int
    _to_float = workflow_to_float
    _truncate_text = workflow_truncate_text
    _decode_data_url = workflow_decode_data_url
    _decode_bytes_to_text = workflow_decode_bytes_to_text
    _dict_rows_to_csv = workflow_dict_rows_to_csv
    _build_text_preview = workflow_build_text_preview
    _normalize_header_token = workflow_normalize_header_token
    _resolve_column_by_alias = workflow_resolve_column_by_alias
    _parse_numeric_value = workflow_parse_numeric_value
    _normalize_text_value = workflow_normalize_text_value
    _parse_ratio_value = workflow_parse_ratio_value
    _parse_boolean_value = workflow_parse_boolean_value
    _safe_ratio = workflow_safe_ratio
    _format_money = workflow_format_money
    _format_ratio = workflow_format_ratio
    _match_amazon_ads_columns = workflow_match_amazon_ads_columns
    _build_amazon_ads_decision_board = workflow_build_amazon_ads_decision_board
    _build_amazon_ads_validation_summary = workflow_build_amazon_ads_validation_summary
    _run_amazon_ads_keyword_optimize_tool = workflow_run_amazon_ads_keyword_optimize_tool
    _build_inline_agent = workflow_build_inline_agent
    _should_use_adk_runtime = workflow_should_use_adk_runtime
    _run_adk_text_chat = workflow_run_adk_text_chat
    _get_workflow_user_id = workflow_get_workflow_user_id
    _extract_agent_card_defaults = workflow_extract_agent_card_defaults
    _extract_agent_llm_defaults = workflow_extract_agent_llm_defaults
    _resolve_llm_default_value = workflow_resolve_llm_default_value
    _invoke_llm_chat = workflow_invoke_llm_chat
    _create_provider_service = workflow_create_provider_service
    _is_active_inline_provider_token = workflow_is_active_inline_provider_token
    _is_auto_inline_model_token = workflow_is_auto_inline_model_token
    _should_resolve_inline_from_active_profile = workflow_should_resolve_inline_from_active_profile
    _select_profile_target_for_agent_task = workflow_select_profile_target_for_agent_task
    _get_user_profiles = workflow_get_user_profiles
    _generate_workflow_frontend_session_id = workflow_generate_workflow_frontend_session_id
    _extract_model_version = workflow_extract_model_version
    _is_candidate_for_agent_task = workflow_is_candidate_for_agent_task
    _rank_model_for_agent_task = workflow_rank_model_for_agent_task
    _resolve_preferred_model_for_agent_task = workflow_resolve_preferred_model_for_agent_task
    _looks_like_image_generation_model = workflow_looks_like_image_generation_model
    _looks_like_image_edit_model = workflow_looks_like_image_edit_model
    _looks_like_video_generation_model = workflow_looks_like_video_generation_model
    _looks_like_audio_generation_model = workflow_looks_like_audio_generation_model
    _looks_like_google_chat_image_edit_model = workflow_looks_like_google_chat_image_edit_model
    _looks_like_vision_understand_model = workflow_looks_like_vision_understand_model
    _list_saved_model_ids = workflow_list_saved_model_ids
    _get_default_image_model = workflow_get_default_image_model
    _get_default_video_model = workflow_get_default_video_model
    _get_default_audio_model = workflow_get_default_audio_model
    _select_image_model = workflow_select_image_model
    _looks_like_text_model = workflow_looks_like_text_model
    _default_text_model_for_provider = workflow_default_text_model_for_provider
    _select_text_chat_target = workflow_select_text_chat_target
    _rank_provider_profiles_for_tool = workflow_rank_provider_profiles_for_tool
    _select_provider_profile_for_tool = workflow_select_provider_profile_for_tool
    _is_usable_requested_image_model = workflow_is_usable_requested_image_model
    _resolve_image_model_for_profile = workflow_resolve_image_model_for_profile
    _list_candidate_image_models = workflow_list_candidate_image_models
    _create_tool_provider_service = workflow_create_tool_provider_service
    _looks_like_excel_binary = workflow_looks_like_excel_binary
    _parse_reference_ip_host = workflow_parse_reference_ip_host
    _is_disallowed_reference_ip = workflow_is_disallowed_reference_ip
    _is_disallowed_reference_hostname = workflow_is_disallowed_reference_hostname
    _resolve_generic_path = workflow_resolve_generic_path
    _normalize_possible_image_url = workflow_normalize_possible_image_url
    _normalize_possible_file_url = workflow_normalize_possible_file_url
    _normalize_possible_result_media_url = workflow_normalize_possible_result_media_url
    _normalize_reference_image_for_provider = workflow_normalize_reference_image_for_provider
    _build_source_video_payload = workflow_build_source_video_payload
    _guess_image_mime_type_from_reference = workflow_guess_image_mime_type_from_reference
    _extract_all_image_urls = workflow_extract_all_image_urls
    _extract_result_image_urls = workflow_extract_result_image_urls
    _extract_first_image_url = workflow_extract_first_image_url
    _extract_first_video_url = workflow_extract_first_video_url
    _resolve_agent_reference_image_url = workflow_resolve_agent_reference_image_url
    _resolve_agent_source_video_input = workflow_resolve_agent_source_video_input
    _resolve_agent_source_video_url = workflow_resolve_agent_source_video_url
    _get_tool_arg = workflow_get_tool_arg
    _to_bool = workflow_to_bool
    _normalize_resolution_tier = workflow_normalize_resolution_tier
    _resolve_google_image_size = workflow_resolve_google_image_size
    _resolve_tongyi_resolution = workflow_resolve_tongyi_resolution
    _resolve_generic_image_size = workflow_resolve_generic_image_size
    _build_generate_kwargs = workflow_build_generate_kwargs
    _resolve_video_resolution = workflow_resolve_video_resolution
    _guess_audio_mime_type = workflow_guess_audio_mime_type
    _build_image_edit_kwargs = workflow_build_image_edit_kwargs
    _run_image_generate_tool = workflow_run_image_generate_tool
    _run_image_edit_tool = workflow_run_image_edit_tool
    _sanitize_vision_text_prompt = workflow_sanitize_vision_text_prompt
    _build_vision_understand_prompt = workflow_build_vision_understand_prompt
    _build_vision_understand_summary = workflow_build_vision_understand_summary
    _run_vision_understand_task = workflow_run_vision_understand_task
    _build_guarded_edit_prompt = workflow_build_guarded_edit_prompt
    _extract_json_object_from_text = workflow_extract_json_object_from_text
    _select_google_vision_eval_model = workflow_select_google_vision_eval_model
    _validate_image_edit_result = workflow_validate_image_edit_result
    _run_sheet_analyze_tool = workflow_run_sheet_analyze_tool
    _run_prompt_optimize_tool = workflow_run_prompt_optimize_tool
    _run_table_analyze_tool = workflow_run_table_analyze_tool

    _record_trace_event = workflow_record_trace_event
    _emit_callback = workflow_emit_callback
    _resolve_agent_timeout_seconds = workflow_resolve_agent_timeout_seconds
    execute = workflow_execute
    _execute_node = workflow_execute_node
    _execute_agent_node = workflow_execute_agent_node

    def _validate_remote_reference_url(self, ref_text: str) -> str:
        return workflow_validate_remote_reference_url(self, ref_text)

    def _load_binary_from_reference(
        self,
        ref: str,
        max_bytes: int = 8 * 1024 * 1024,
    ) -> Tuple[bytes, str, str]:
        return workflow_load_binary_from_reference(self, ref=ref, max_bytes=max_bytes)

    def _normalize_dataframe(self, frame: Any) -> Any:
        return workflow_normalize_dataframe(self, frame)

    def _text_to_dataframe(self, text: str, source_hint: str = "") -> Any:
        return workflow_text_to_dataframe(self, text=text, source_hint=source_hint)

    def _bytes_to_dataframe(self, raw: bytes, mime_type: str = "", file_name: str = "") -> Any:
        return workflow_bytes_to_dataframe(self, raw=raw, mime_type=mime_type, file_name=file_name)

    def _table_payload_to_dataframe(self, payload: Any) -> Tuple[Any, str]:
        return workflow_table_payload_to_dataframe(self, payload)

    def _table_payload_to_text(self, payload: Any) -> Tuple[str, str]:
        return workflow_table_payload_to_text(self, payload)

    def _build_file_reference_context(self, file_ref: str) -> str:
        return workflow_build_file_reference_context(self, file_ref)

    def _build_video_generate_kwargs(self, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        return workflow_build_video_generate_kwargs(self, tool_args)

    def _build_audio_generate_kwargs(self, tool_args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return workflow_build_audio_generate_kwargs(self, tool_args)

    def _normalize_video_service_result(self, raw_result: Any) -> Dict[str, Any]:
        return workflow_normalize_video_service_result(self, raw_result)

    def _normalize_audio_service_result(
        self,
        raw_result: Any,
        fallback_format: str = "mp3",
    ) -> Dict[str, Any]:
        return workflow_normalize_audio_service_result(self, raw_result, fallback_format=fallback_format)

    async def _run_video_generate_task(
        self,
        *,
        provider_id: str,
        model_id: str,
        profile_id: str,
        prompt: str,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await workflow_run_video_generate_task(
            self,
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            prompt=prompt,
            tool_args=tool_args,
        )

    async def _run_video_understand_task(
        self,
        *,
        provider_id: str,
        model_id: str,
        profile_id: str,
        prompt: str,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await workflow_run_video_understand_task(
            self,
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            prompt=prompt,
            tool_args=tool_args,
        )

    async def _run_video_delete_task(
        self,
        *,
        provider_id: str,
        profile_id: str,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await workflow_run_video_delete_task(
            self,
            provider_id=provider_id,
            profile_id=profile_id,
            tool_args=tool_args,
        )

    async def _run_audio_generate_task(
        self,
        *,
        provider_id: str,
        model_id: str,
        profile_id: str,
        text: str,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await workflow_run_audio_generate_task(
            self,
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            text=text,
            tool_args=tool_args,
        )

    def _normalize_image_edit_mode(
        self,
        mode_value: Any,
        provider_id: str,
        is_outpaint: bool,
    ) -> Optional[str]:
        return workflow_normalize_image_edit_mode(mode_value, provider_id=provider_id, is_outpaint=is_outpaint)

    def _normalize_mode_token_for_routing(self, mode_value: Any) -> str:
        return workflow_normalize_mode_token_for_routing(mode_value)

    def _is_outpaint_mode_token(self, normalized_mode: str) -> bool:
        return workflow_is_outpaint_mode_token(normalized_mode)

    def _resolve_image_tool_route(
        self,
        normalized_tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        return workflow_resolve_image_tool_route(self, normalized_tool_name=normalized_tool_name, tool_args=tool_args)

    def _normalize_image_service_results(self, raw_result: Any) -> Dict[str, Any]:
        return workflow_normalize_image_service_results(self, raw_result)

    def _trim_normalized_images(self, normalized: Dict[str, Any], keep_last: int = 1) -> Dict[str, Any]:
        return workflow_trim_normalized_images(normalized, keep_last=keep_last)

    def _normalize_search_items(self, payload: Any, max_items: int) -> List[Dict[str, str]]:
        return workflow_normalize_search_items(payload, max_items=max_items)

    def _fetch_duckduckgo_results(self, query: str, region: str) -> List[Dict[str, str]]:
        return workflow_fetch_duckduckgo_results(query, region)

    async def _run_web_search_tool(
        self,
        tool_args: Dict[str, Any],
        latest_input: Any,
    ) -> Dict[str, Any]:
        return await workflow_run_web_search_tool(self, tool_args=tool_args, latest_input=latest_input)

    def _extract_mcp_server_map(self, root: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return workflow_extract_mcp_server_map(root)

    def _normalize_mcp_args_list(self, raw_args: Any) -> Optional[List[str]]:
        return workflow_normalize_mcp_args_list(raw_args)

    def _normalize_mcp_env_map(self, raw_env: Any) -> Optional[Dict[str, str]]:
        return workflow_normalize_mcp_env_map(raw_env)

    def _load_workflow_mcp_server_config(
        self,
        requested_server_key: str = "",
    ) -> Tuple[str, Any, str]:
        return workflow_load_workflow_mcp_server_config(self, requested_server_key=requested_server_key)

    async def _run_mcp_tool_call(
        self,
        tool_args: Dict[str, Any],
        latest_input: Any,
    ) -> Dict[str, Any]:
        return await workflow_run_mcp_tool_call(self, tool_args=tool_args, latest_input=latest_input)

    async def _run_read_webpage_tool(
        self,
        tool_args: Dict[str, Any],
        latest_input: Any,
    ) -> Dict[str, Any]:
        return await workflow_run_read_webpage_tool(self, tool_args=tool_args, latest_input=latest_input)

    async def _run_selenium_browse_tool(
        self,
        tool_args: Dict[str, Any],
        latest_input: Any,
    ) -> Dict[str, Any]:
        return await workflow_run_selenium_browse_tool(self, tool_args=tool_args, latest_input=latest_input)

    async def _execute_builtin_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        context: ExecutionContext,
        input_packets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return await workflow_execute_builtin_tool(
            self,
            tool_name=tool_name,
            tool_args=tool_args,
            context=context,
            input_packets=input_packets,
        )

    def _get_sheet_stage_artifact_service(self):
        return workflow_get_sheet_stage_artifact_service(self)

    def _extract_sheet_stage_artifact_ref_from_value(
        self,
        value: Any,
        depth: int = 0,
    ) -> Optional[Dict[str, Any]]:
        return workflow_extract_sheet_stage_artifact_ref_from_value(self, value, depth=depth)

    def _extract_sheet_stage_session_id_from_value(
        self,
        value: Any,
        depth: int = 0,
    ) -> str:
        return workflow_extract_sheet_stage_session_id_from_value(self, value, depth=depth)

    def _build_sheet_stage_request_payload(
        self,
        *,
        stage: str,
        tool_args: Dict[str, Any],
        latest_input: Any,
    ) -> Dict[str, Any]:
        return workflow_build_sheet_stage_request_payload(
            self,
            stage=stage,
            tool_args=tool_args,
            latest_input=latest_input,
        )

    async def _run_sheet_stage_tool(
        self,
        *,
        normalized_tool_name: str,
        tool_args: Dict[str, Any],
        latest_input: Any,
    ) -> Dict[str, Any]:
        return await workflow_run_sheet_stage_tool(
            self,
            normalized_tool_name=normalized_tool_name,
            tool_args=tool_args,
            latest_input=latest_input,
        )
