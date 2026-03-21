"""
Agent node execution extracted from WorkflowEngine.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from ..execution_context import ExecutionContext

logger = logging.getLogger(__name__)


async def execute_agent_node(
    engine: Any,
    node_id: str,
    node_data: Dict[str, Any],
    context: ExecutionContext,
    initial_input: Dict[str, Any],
    input_packets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from ....models.db_models import AgentRegistry

    agent_id = node_data.get("agent_id") or node_data.get("agentId") or ""
    agent_name = node_data.get("agent_name") or node_data.get("agentName") or ""
    agent = None
    user_id = engine._get_workflow_user_id()

    if agent_id:
        cache_key = (user_id, str(agent_id).strip())
        agent = engine._agent_cache_by_id.get(cache_key)
        if not agent:
            query = engine.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id,
                AgentRegistry.status == "active",
            )
            if user_id:
                query = query.filter(AgentRegistry.user_id == user_id)
            agent = query.first()
            if agent:
                engine._agent_cache_by_id[cache_key] = agent

    if not agent and agent_name:
        normalized_name = str(agent_name or "").strip().lower()
        cache_key = (user_id, normalized_name)
        agent = engine._agent_cache_by_name.get(cache_key)
        if not agent and user_id:
            agent = engine.db.query(AgentRegistry).filter(
                AgentRegistry.user_id == user_id,
                AgentRegistry.name == agent_name,
                AgentRegistry.status == "active",
            ).first()
            if agent:
                engine._agent_cache_by_name[cache_key] = agent

    if not agent:
        agent = engine._build_inline_agent(node_id=node_id, node_data=node_data)

    if not agent:
        raise ValueError(f"Agent 节点 {node_id} 未找到匹配的 Agent（id={agent_id}, name={agent_name}）")

    agent_card_defaults: Dict[str, Any] = engine._extract_agent_card_defaults(agent)
    llm_defaults: Dict[str, Any] = engine._extract_agent_llm_defaults(agent_card_defaults)

    model_override_provider = (
        node_data.get("model_override_provider_id")
        or node_data.get("modelOverrideProviderId")
        or node_data.get("override_provider_id")
        or node_data.get("overrideProviderId")
        or ""
    )
    model_override_model = (
        node_data.get("model_override_model_id")
        or node_data.get("modelOverrideModelId")
        or node_data.get("override_model_id")
        or node_data.get("overrideModelId")
        or ""
    )
    model_override_profile = (
        node_data.get("model_override_profile_id")
        or node_data.get("modelOverrideProfileId")
        or node_data.get("override_profile_id")
        or node_data.get("overrideProfileId")
        or ""
    )
    inline_override_provider = (
        node_data.get("inlineProviderId")
        or node_data.get("inline_provider_id")
        or ""
    )
    inline_override_model = (
        node_data.get("inlineModelId")
        or node_data.get("inline_model_id")
        or ""
    )
    inline_override_profile = (
        node_data.get("inlineProfileId")
        or node_data.get("inline_profile_id")
        or ""
    )

    llm_default_provider = str(
        engine._resolve_llm_default_value(llm_defaults, "providerId", "provider_id")
        or ""
    ).strip()
    llm_default_model = str(
        engine._resolve_llm_default_value(llm_defaults, "modelId", "model_id")
        or ""
    ).strip()
    llm_default_profile = str(
        engine._resolve_llm_default_value(llm_defaults, "profileId", "profile_id")
        or ""
    ).strip()
    llm_default_system_prompt = str(
        engine._resolve_llm_default_value(llm_defaults, "systemPrompt", "system_prompt")
        or ""
    ).strip()

    provider_id = (
        str(model_override_provider).strip()
        or llm_default_provider
        or str(agent.provider_id or "").strip()
    )
    model_id = (
        str(model_override_model).strip()
        or llm_default_model
        or str(agent.model_id or "").strip()
    )
    profile_id = str(model_override_profile).strip() or llm_default_profile
    if not provider_id or not model_id:
        raise ValueError(f"Agent {agent.name} 未配置可用的 LLM 提供商或模型")

    node_temperature_raw = (
        node_data.get("agent_temperature")
        or node_data.get("agentTemperature")
        or node_data.get("temperature")
    )
    node_max_tokens_raw = (
        node_data.get("agent_max_tokens")
        or node_data.get("agentMaxTokens")
        or node_data.get("max_tokens")
        or node_data.get("maxTokens")
    )
    llm_default_temperature = engine._to_float(
        engine._resolve_llm_default_value(llm_defaults, "temperature"),
        default=None,
    )
    llm_default_max_tokens = engine._to_int(
        engine._resolve_llm_default_value(llm_defaults, "maxTokens", "max_tokens"),
        default=None,
        minimum=1,
        maximum=65536,
    )
    agent_temperature = engine._to_float(node_temperature_raw, default=None)
    if agent_temperature is None:
        agent_temperature = llm_default_temperature
    if agent_temperature is None:
        agent_temperature = engine._to_float(getattr(agent, "temperature", None), default=0.7)
    if agent_temperature is None:
        agent_temperature = 0.7

    agent_max_tokens = engine._to_int(
        node_max_tokens_raw,
        default=None,
        minimum=1,
        maximum=65536,
    )
    if agent_max_tokens is None:
        agent_max_tokens = llm_default_max_tokens
    if agent_max_tokens is None:
        agent_max_tokens = engine._to_int(getattr(agent, "max_tokens", None), default=4096, minimum=1, maximum=65536)
    if agent_max_tokens is None:
        agent_max_tokens = 4096

    input_mapping = node_data.get("input_mapping") or node_data.get("inputMapping") or ""
    latest_input_payload: Any = None
    if isinstance(input_mapping, str) and input_mapping.strip():
        mapped = context.resolve_template(input_mapping)
        latest_input_payload = mapped
        previous_text = engine._extract_text_from_value(mapped)
    else:
        latest_input_payload = input_packets[-1].get("output") if input_packets else context.get_latest_output()
        previous_text = engine._derive_node_input_text(context, initial_input, input_packets)

    if not previous_text:
        previous_text = initial_input.get("task", "") or initial_input.get("input", "")
    if latest_input_payload is None:
        latest_input_payload = initial_input

    base_prompt = llm_default_system_prompt or (agent.system_prompt or "")
    node_instructions = node_data.get("instructions") or ""
    if node_instructions.strip():
        system_prompt = f"{base_prompt}\n\n--- 节点附加指令 ---\n{node_instructions}".strip()
    else:
        system_prompt = base_prompt

    default_task_type = str(agent_card_defaults.get("defaultTaskType") or "").strip()
    explicit_task_type = (
        node_data.get("agent_task_type")
        or node_data.get("agentTaskType")
        or ""
    )
    has_explicit_task_type = bool(str(explicit_task_type or "").strip())
    agent_task_type = (
        explicit_task_type
        or default_task_type
        or "chat"
    ).strip()
    normalized_agent_task_type = str(agent_task_type or "").strip().lower().replace("_", "-")

    if not has_explicit_task_type and normalized_agent_task_type == "image-edit":
        reference_image_hint = (
            node_data.get("agentReferenceImageUrl")
            or node_data.get("agent_reference_image_url")
            or ""
        )
        if not str(reference_image_hint or "").strip():
            logger.info(
                "[WorkflowEngine] Agent '%s' node '%s' defaulted to image-edit without reference image; fallback to chat",
                agent.name,
                node_id,
            )
            agent_task_type = "chat"
            normalized_agent_task_type = "chat"

    explicit_reference_image_url = (
        node_data.get("agentReferenceImageUrl")
        or node_data.get("agent_reference_image_url")
        or ""
    )
    if str(explicit_reference_image_url or "").strip():
        if normalized_agent_task_type not in {
            "vision-understand",
            "image-understand",
            "vision-analyze",
            "image-analyze",
            "image-edit",
            "video-gen",
        }:
            raise ValueError(
                f"节点 {node_id} 配置了参考图，但 agentTaskType={agent_task_type}。"
                "开发阶段不允许兼容推断，请显式设置为 vision-understand、image-edit 或 video-gen。"
            )

    has_explicit_inline_override = (
        str(getattr(agent, "agent_type", "") or "").strip().lower() == "inline"
        and bool(
            str(inline_override_profile or "").strip()
            or (
                str(inline_override_provider or "").strip()
                and not engine._is_active_inline_provider_token(inline_override_provider)
            )
            or (
                str(inline_override_model or "").strip()
                and not engine._is_auto_inline_model_token(inline_override_model)
            )
        )
    )
    has_explicit_model_override = bool(
        str(model_override_model or "").strip()
        or str(model_override_provider or "").strip()
        or str(model_override_profile or "").strip()
        or has_explicit_inline_override
    )
    model_overridden = has_explicit_model_override
    seed_default_prefer_latest = str(getattr(agent, "agent_type", "") or "").strip().lower() == "seed"
    llm_default_prefer_latest = engine._resolve_llm_default_value(
        llm_defaults,
        "preferLatestModel",
        "prefer_latest_model",
    )
    default_prefer_latest = engine._to_bool(
        llm_default_prefer_latest if llm_default_prefer_latest is not None else agent_card_defaults.get("preferLatestModel"),
        default=seed_default_prefer_latest,
    )
    prefer_latest_raw = node_data.get("agentPreferLatestModel", node_data.get("agent_prefer_latest_model"))
    if prefer_latest_raw is None:
        prefer_latest_model = default_prefer_latest and not has_explicit_model_override
    else:
        prefer_latest_model = engine._to_bool(prefer_latest_raw, default=default_prefer_latest)

    preferred_mode_hint = (
        node_data.get("agentEditMode")
        or node_data.get("agent_edit_mode")
        or ""
    )
    if prefer_latest_model:
        resolved_model = engine._resolve_preferred_model_for_agent_task(
            provider_id=provider_id,
            requested_model=model_id,
            agent_task_type=agent_task_type,
            preferred_mode=preferred_mode_hint,
            preferred_profile_id=profile_id,
        )
        if resolved_model and resolved_model != model_id:
            logger.info(
                f"[WorkflowEngine] Agent '{agent.name}' auto model switch: {model_id} -> {resolved_model}"
            )
            model_id = resolved_model

    model_is_compatible = engine._is_candidate_for_agent_task(
        model_id=model_id,
        agent_task_type=agent_task_type,
        preferred_mode=preferred_mode_hint,
    )
    if not model_is_compatible:
        if has_explicit_model_override:
            raise ValueError(
                f"节点 {node_id} 显式配置模型 {model_id} 与 agentTaskType={agent_task_type} 不兼容"
            )
        normalized_task_for_model = str(agent_task_type or "").strip().lower().replace("_", "-")
        resolved_model = ""
        if normalized_task_for_model in {"", "chat", "data-analysis", "table-analysis"}:
            resolved_model = engine._default_text_model_for_provider(provider_id)
        if not resolved_model:
            resolved_model = engine._resolve_preferred_model_for_agent_task(
                provider_id=provider_id,
                requested_model=model_id,
                agent_task_type=agent_task_type,
                preferred_mode=preferred_mode_hint,
                preferred_profile_id=profile_id,
            )
        if resolved_model and resolved_model != model_id:
            logger.info(
                "[WorkflowEngine] Agent '%s' corrected incompatible model: %s -> %s (taskType=%s)",
                agent.name,
                model_id,
                resolved_model,
                agent_task_type,
            )
            model_id = resolved_model

        if not engine._is_candidate_for_agent_task(
            model_id=model_id,
            agent_task_type=agent_task_type,
            preferred_mode=preferred_mode_hint,
        ):
            raise ValueError(
                f"节点 {node_id} 没有可用模型可匹配 agentTaskType={agent_task_type}（当前模型: {model_id}）"
            )

    logger.info(
        f"[WorkflowEngine] Executing agent '{agent.name}' taskType={agent_task_type} model={provider_id}/{model_id}"
        + (f" profile={profile_id}" if profile_id else "")
    )

    if normalized_agent_task_type in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
        reference_image_url = engine._resolve_agent_reference_image_url(
            node_data=node_data,
            context=context,
            initial_input=initial_input,
            input_packets=input_packets,
        )
        if not reference_image_url:
            raise ValueError(
                f"图片理解节点 {node_id} 缺少参考图，请配置 agentReferenceImageUrl 或在上游提供 imageUrl"
            )

        vision_result = await engine._run_vision_understand_task(
            provider_id=provider_id,
            model_id=model_id,
            system_prompt=system_prompt,
            prompt=previous_text,
            source_image_url=reference_image_url,
            temperature=agent_temperature,
            max_tokens=agent_max_tokens,
            profile_id=profile_id,
        )
        vision_defaults = agent_card_defaults.get("visionUnderstand") if isinstance(agent_card_defaults.get("visionUnderstand"), dict) else {}
        vision_output_format = str(
            node_data.get("agentOutputFormat")
            or node_data.get("agent_output_format")
            or (vision_defaults.get("outputFormat") if isinstance(vision_defaults, dict) else "")
            or "json"
        ).strip().lower()
        if vision_output_format not in {"text", "json", "markdown"}:
            vision_output_format = "json"
        vision_analysis = vision_result.get("analysis") if isinstance(vision_result.get("analysis"), dict) else {}
        vision_text = str(vision_result.get("text") or "").strip()
        if vision_output_format == "json" and vision_analysis:
            vision_text = json.dumps(vision_analysis, ensure_ascii=False)
        elif vision_output_format == "markdown" and vision_analysis:
            markdown_lines: List[str] = []
            for key, value in vision_analysis.items():
                key_text = str(key or "").strip()
                if not key_text:
                    continue
                if isinstance(value, list):
                    bullet_items = [str(item).strip() for item in value if str(item).strip()]
                    if bullet_items:
                        markdown_lines.append(f"- **{key_text}**: " + " / ".join(bullet_items))
                    continue
                value_text = str(value or "").strip()
                if value_text:
                    markdown_lines.append(f"- **{key_text}**: {value_text}")
            if markdown_lines:
                vision_text = "\n".join(markdown_lines)
        return {
            "text": vision_text,
            "agentName": agent.name,
            "agentTaskType": normalized_agent_task_type,
            "model": f"{provider_id}/{model_id}",
            "baseModel": f"{agent.provider_id}/{agent.model_id}" if agent.provider_id and agent.model_id else "",
            "modelOverridden": model_overridden,
            "profileId": profile_id,
            "runtime": "multimodal",
            "outputFormat": vision_output_format,
            **{k: v for k, v in vision_result.items() if k not in {"text"}},
        }

    if normalized_agent_task_type in {"image-gen", "image-edit"}:
        tool_args: Dict[str, Any] = {
            "prompt": previous_text,
            "model_id": model_id,
        }
        image_generation_defaults = agent_card_defaults.get("imageGeneration")
        image_edit_defaults = agent_card_defaults.get("imageEdit")

        def _has_effective_value(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                stripped = value.strip()
                return bool(stripped) and stripped != "-1"
            return True

        default_image_options = (
            image_edit_defaults if normalized_agent_task_type == "image-edit" else image_generation_defaults
        )
        if isinstance(default_image_options, dict):
            default_to_tool_map = {
                "aspectRatio": "aspect_ratio",
                "imageSize": "image_size",
                "resolutionTier": "resolution",
                "numberOfImages": "number_of_images",
                "imageStyle": "image_style",
                "outputMimeType": "output_mime_type",
                "negativePrompt": "negative_prompt",
                "seed": "seed",
                "promptExtend": "prompt_extend",
                "addMagicSuffix": "add_magic_suffix",
            }
            if normalized_agent_task_type == "image-edit":
                default_to_tool_map.update({
                    "editMode": "mode",
                    "outputLanguage": "output_language",
                    "maxRetries": "max_retries",
                    "preserveProductIdentity": "preserve_product_identity",
                    "productMatchThreshold": "product_match_threshold",
                })
            for src_key, dst_key in default_to_tool_map.items():
                default_value = default_image_options.get(src_key)
                if _has_effective_value(default_value):
                    tool_args[dst_key] = default_value

        agent_field_map = {
            "agentAspectRatio": "aspect_ratio",
            "agentImageSize": "image_size",
            "agentResolutionTier": "resolution",
            "agentNumberOfImages": "number_of_images",
            "agentImageStyle": "image_style",
            "agentOutputMimeType": "output_mime_type",
            "agentNegativePrompt": "negative_prompt",
            "agentSeed": "seed",
            "agentPromptExtend": "prompt_extend",
            "agentAddMagicSuffix": "add_magic_suffix",
            "agent_aspect_ratio": "aspect_ratio",
            "agent_image_size": "image_size",
            "agent_resolution_tier": "resolution",
            "agent_number_of_images": "number_of_images",
            "agent_image_style": "image_style",
            "agent_output_mime_type": "output_mime_type",
            "agent_negative_prompt": "negative_prompt",
            "agent_seed": "seed",
            "agent_prompt_extend": "prompt_extend",
            "agent_add_magic_suffix": "add_magic_suffix",
            "agentEditMode": "mode",
            "agent_edit_mode": "mode",
            "agentOutputLanguage": "output_language",
            "agent_output_language": "output_language",
            "agentImageEditMaxRetries": "max_retries",
            "agent_image_edit_max_retries": "max_retries",
        }
        for src_key, dst_key in agent_field_map.items():
            val = node_data.get(src_key)
            if _has_effective_value(val):
                tool_args[dst_key] = val

        tool_args["provider_id"] = provider_id
        if profile_id:
            tool_args["profile_id"] = profile_id

        latest_input = previous_text
        if normalized_agent_task_type == "image-edit":
            ref_url = (
                node_data.get("agentReferenceImageUrl")
                or node_data.get("agent_reference_image_url")
                or ""
            )
            if ref_url and ref_url.strip():
                resolved_ref = context.resolve_template(ref_url) if "{{" in ref_url else ref_url
                tool_args["image_url"] = str(resolved_ref).strip()
            edit_prompt = (
                node_data.get("agentEditPrompt")
                or node_data.get("agent_edit_prompt")
                or ""
            )
            if edit_prompt and edit_prompt.strip():
                tool_args["edit_prompt"] = edit_prompt.strip()
            if isinstance(image_edit_defaults, dict):
                default_edit_mode = image_edit_defaults.get("editMode")
                if default_edit_mode and engine._get_tool_arg(tool_args, "mode", "edit_mode", "editMode") is None:
                    tool_args["mode"] = default_edit_mode

            preserve_product_identity = engine._to_bool(
                node_data.get(
                    "agentPreserveProductIdentity",
                    node_data.get(
                        "agent_preserve_product_identity",
                        engine._get_tool_arg(
                            tool_args,
                            "preserve_product_identity",
                            "preserveProductIdentity",
                        ),
                    ),
                ),
                default=True,
            )
            tool_args["preserve_product_identity"] = preserve_product_identity
            max_retries = engine._to_int(
                node_data.get(
                    "agentImageEditMaxRetries",
                    node_data.get(
                        "agent_image_edit_max_retries",
                        engine._get_tool_arg(tool_args, "max_retries", "maxRetries"),
                    ),
                ),
                default=1,
                minimum=0,
                maximum=3,
            )
            tool_args["max_retries"] = max_retries if max_retries is not None else 1

            product_match_threshold = engine._to_int(
                node_data.get(
                    "agentProductMatchThreshold",
                    node_data.get(
                        "agent_product_match_threshold",
                        engine._get_tool_arg(
                            tool_args,
                            "product_match_threshold",
                            "productMatchThreshold",
                        ),
                    ),
                ),
                default=70,
                minimum=50,
                maximum=95,
            )
            if product_match_threshold is not None:
                tool_args["product_match_threshold"] = product_match_threshold

            preferred_mode = str(
                engine._get_tool_arg(tool_args, "mode", "edit_mode", "editMode") or ""
            ).strip()
            image_result = await engine._run_image_edit_tool(
                tool_args,
                latest_input,
                preferred_mode=preferred_mode,
            )
        else:
            image_result = await engine._run_image_generate_tool(tool_args, latest_input)

        summary_text = str(
            image_result.get("summaryText")
            or image_result.get("summary_text")
            or image_result.get("text")
            or previous_text
        ).strip()

        return {
            "text": summary_text,
            "prompt": image_result.get("prompt", previous_text),
            "agentName": agent.name,
            "agentTaskType": normalized_agent_task_type,
            "model": f"{provider_id}/{model_id}",
            "baseModel": f"{agent.provider_id}/{agent.model_id}" if agent.provider_id and agent.model_id else "",
            "modelOverridden": model_overridden,
            "profileId": profile_id,
            **{k: v for k, v in image_result.items() if k not in ("prompt",)},
        }

    if normalized_agent_task_type == "video-gen":
        tool_args = {
            "prompt": previous_text or "生成一段视频",
            "model_id": model_id,
            "provider_id": provider_id,
        }
        if profile_id:
            tool_args["profile_id"] = profile_id

        video_generation_defaults = (
            agent_card_defaults.get("videoGeneration")
            if isinstance(agent_card_defaults.get("videoGeneration"), dict)
            else {}
        )
        default_to_tool_map = {
            "aspectRatio": "aspect_ratio",
            "resolution": "resolution",
            "durationSeconds": "duration_seconds",
            "videoExtensionCount": "video_extension_count",
            "negativePrompt": "negative_prompt",
            "seed": "seed",
            "promptExtend": "prompt_extend",
            "generateAudio": "generate_audio",
            "personGeneration": "person_generation",
            "subtitleMode": "subtitle_mode",
            "subtitleLanguage": "subtitle_language",
            "subtitleScript": "subtitle_script",
            "storyboardPrompt": "storyboard_prompt",
            "continueFromPreviousVideo": "continue_from_previous_video",
            "continueFromPreviousLastFrame": "continue_from_previous_last_frame",
            "videoMaskMode": "video_mask_mode",
        }
        for src_key, dst_key in default_to_tool_map.items():
            default_value = video_generation_defaults.get(src_key)
            if default_value is None:
                continue
            if isinstance(default_value, str) and not default_value.strip():
                continue
            tool_args[dst_key] = default_value

        node_field_map = {
            "agentAspectRatio": "aspect_ratio",
            "agent_aspect_ratio": "aspect_ratio",
            "agentVideoAspectRatio": "aspect_ratio",
            "agent_video_aspect_ratio": "aspect_ratio",
            "agentResolutionTier": "resolution",
            "agent_resolution_tier": "resolution",
            "agentVideoResolution": "resolution",
            "agent_video_resolution": "resolution",
            "agentVideoDurationSeconds": "duration_seconds",
            "agent_video_duration_seconds": "duration_seconds",
            "agentVideoExtensionCount": "video_extension_count",
            "agent_video_extension_count": "video_extension_count",
            "agentNegativePrompt": "negative_prompt",
            "agent_negative_prompt": "negative_prompt",
            "agentSeed": "seed",
            "agent_seed": "seed",
            "agentPromptExtend": "prompt_extend",
            "agent_prompt_extend": "prompt_extend",
            "agentGenerateAudio": "generate_audio",
            "agent_generate_audio": "generate_audio",
            "agentPersonGeneration": "person_generation",
            "agent_person_generation": "person_generation",
            "agentSubtitleMode": "subtitle_mode",
            "agent_subtitle_mode": "subtitle_mode",
            "agentSubtitleLanguage": "subtitle_language",
            "agent_subtitle_language": "subtitle_language",
            "agentSubtitleScript": "subtitle_script",
            "agent_subtitle_script": "subtitle_script",
            "agentStoryboardPrompt": "storyboard_prompt",
            "agent_storyboard_prompt": "storyboard_prompt",
            "agentContinueFromPreviousVideo": "continue_from_previous_video",
            "agent_continue_from_previous_video": "continue_from_previous_video",
            "agentContinueFromPreviousLastFrame": "continue_from_previous_last_frame",
            "agent_continue_from_previous_last_frame": "continue_from_previous_last_frame",
            "agentVideoMaskMode": "video_mask_mode",
            "agent_video_mask_mode": "video_mask_mode",
        }
        for src_key, dst_key in node_field_map.items():
            value = node_data.get(src_key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            tool_args[dst_key] = value

        source_video_input = engine._resolve_agent_source_video_input(
            node_data,
            context,
            initial_input,
            input_packets,
        )
        if source_video_input is not None:
            tool_args["source_video"] = source_video_input
        source_image_url = engine._resolve_agent_reference_image_url(
            node_data=node_data,
            context=context,
            initial_input=initial_input,
            input_packets=input_packets,
        )
        if source_image_url:
            tool_args["source_image"] = source_image_url
        raw_last_frame_image = (
            node_data.get("agentLastFrameImageUrl")
            or node_data.get("agent_last_frame_image_url")
            or ""
        )
        if str(raw_last_frame_image or "").strip():
            resolved_last_frame = (
                context.resolve_template(raw_last_frame_image)
                if isinstance(raw_last_frame_image, str) and "{{" in raw_last_frame_image
                else raw_last_frame_image
            )
            normalized_last_frame = engine._extract_first_image_url(resolved_last_frame)
            if normalized_last_frame:
                tool_args["last_frame_image"] = normalized_last_frame
        raw_video_mask_image = (
            node_data.get("agentVideoMaskImageUrl")
            or node_data.get("agent_video_mask_image_url")
            or ""
        )
        if str(raw_video_mask_image or "").strip():
            resolved_video_mask = (
                context.resolve_template(raw_video_mask_image)
                if isinstance(raw_video_mask_image, str) and "{{" in raw_video_mask_image
                else raw_video_mask_image
            )
            normalized_video_mask = engine._extract_first_image_url(resolved_video_mask)
            if normalized_video_mask:
                tool_args["video_mask_image"] = normalized_video_mask
        if engine._to_bool(tool_args.get("continue_from_previous_last_frame"), default=False):
            tool_args["use_last_frame_bridge"] = True

        video_prompt = str(tool_args.get("prompt") or "").strip() or "生成一段视频"
        video_result = await engine._run_video_generate_task(
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            prompt=video_prompt,
            tool_args=tool_args,
        )
        summary_text = str(
            video_result.get("summaryText")
            or video_result.get("text")
            or "Generated video."
        ).strip() or "Generated video."
        return {
            "text": summary_text,
            "prompt": video_result.get("prompt", video_prompt),
            "agentName": agent.name,
            "agentTaskType": normalized_agent_task_type,
            "model": f"{provider_id}/{model_id}",
            "baseModel": f"{agent.provider_id}/{agent.model_id}" if agent.provider_id and agent.model_id else "",
            "modelOverridden": model_overridden,
            "profileId": profile_id,
            **{k: v for k, v in video_result.items() if k not in ("prompt", "model")},
        }

    if normalized_agent_task_type == "audio-gen":
        tool_args = {
            "model_id": model_id,
            "provider_id": provider_id,
        }
        if profile_id:
            tool_args["profile_id"] = profile_id

        audio_generation_defaults = (
            agent_card_defaults.get("audioGeneration")
            if isinstance(agent_card_defaults.get("audioGeneration"), dict)
            else (
                agent_card_defaults.get("speechGeneration")
                if isinstance(agent_card_defaults.get("speechGeneration"), dict)
                else {}
            )
        )
        default_to_tool_map = {
            "voice": "voice",
            "responseFormat": "response_format",
            "format": "response_format",
            "speed": "speed",
        }
        for src_key, dst_key in default_to_tool_map.items():
            default_value = audio_generation_defaults.get(src_key)
            if default_value is None:
                continue
            if isinstance(default_value, str) and not default_value.strip():
                continue
            tool_args[dst_key] = default_value

        node_field_map = {
            "agentVoice": "voice",
            "agent_voice": "voice",
            "agentAudioFormat": "response_format",
            "agent_audio_format": "response_format",
            "agentSpeechFormat": "response_format",
            "agent_speech_format": "response_format",
            "agentSpeechSpeed": "speed",
            "agent_speech_speed": "speed",
            "agentAudioSpeed": "speed",
            "agent_audio_speed": "speed",
        }
        for src_key, dst_key in node_field_map.items():
            value = node_data.get(src_key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            tool_args[dst_key] = value

        audio_result = await engine._run_audio_generate_task(
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            text=previous_text,
            tool_args=tool_args,
        )
        summary_text = str(
            audio_result.get("summaryText")
            or audio_result.get("text")
            or "Generated speech audio."
        ).strip() or "Generated speech audio."
        return {
            "text": summary_text,
            "agentName": agent.name,
            "agentTaskType": normalized_agent_task_type,
            "model": f"{provider_id}/{model_id}",
            "baseModel": f"{agent.provider_id}/{agent.model_id}" if agent.provider_id and agent.model_id else "",
            "modelOverridden": model_overridden,
            "profileId": profile_id,
            **{k: v for k, v in audio_result.items() if k != "model"},
        }

    if normalized_agent_task_type in {"data-analysis", "table-analysis"}:
        file_url = (
            node_data.get("agentFileUrl")
            or node_data.get("agent_file_url")
            or ""
        )
        if file_url and file_url.strip():
            resolved_url = context.resolve_template(file_url) if "{{" in file_url else file_url
            file_context = engine._build_file_reference_context(str(resolved_url))
            previous_text = f"{file_context}\n\n{previous_text}"

    data_analysis_defaults = (
        agent_card_defaults.get("dataAnalysis")
        if isinstance(agent_card_defaults.get("dataAnalysis"), dict)
        else {}
    )
    output_format = (
        node_data.get("agentOutputFormat")
        or node_data.get("agent_output_format")
        or data_analysis_defaults.get("outputFormat")
        or ""
    )
    if output_format and output_format.strip() and normalized_agent_task_type not in {"image-gen", "image-edit"}:
        previous_text = f"{previous_text}\n\n请以 {output_format} 格式输出结果。"

    if engine._should_use_adk_runtime(agent=agent, provider_id=provider_id, agent_task_type=agent_task_type):
        try:
            adk_response = await engine._run_adk_text_chat(
                agent=agent,
                provider_id=provider_id,
                model_id=model_id,
                system_prompt=system_prompt,
                prompt=previous_text,
                node_id=node_id,
                profile_id=profile_id,
            )
            normalized_text = engine._normalize_agent_response_text(
                text=adk_response.get("text", ""),
                expected_format=str(output_format or ""),
            )
            return {
                "text": normalized_text,
                "agentName": agent.name,
                "agentTaskType": normalized_agent_task_type,
                "model": f"{provider_id}/{model_id}",
                "baseModel": f"{agent.provider_id}/{agent.model_id}" if agent.provider_id and agent.model_id else "",
                "modelOverridden": model_overridden,
                "profileId": profile_id,
                "runtime": "adk",
                "usage": adk_response.get("usage", {}),
                "eventCount": int(adk_response.get("event_count") or 0),
                "adkSessionId": adk_response.get("session_id"),
            }
        except Exception as adk_exc:
            logger.error(
                "[WorkflowEngine] ADK runtime failed for agent '%s' (strict ADK mode): %s",
                agent.name,
                adk_exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"ADK runtime failed for agent '{agent.name}' on node '{node_id}': {adk_exc}"
            ) from adk_exc

    result = await engine._invoke_llm_chat(
        provider_id=provider_id,
        model_id=model_id,
        messages=[{"role": "user", "content": previous_text}],
        system_prompt=system_prompt,
        temperature=agent_temperature,
        max_tokens=agent_max_tokens,
        profile_id=profile_id,
    )

    normalized_text = engine._normalize_agent_response_text(
        text=result.get("text", ""),
        expected_format=str(output_format or ""),
    )

    return {
        "text": normalized_text,
        "agentName": agent.name,
        "agentTaskType": normalized_agent_task_type,
        "model": f"{provider_id}/{model_id}",
        "baseModel": f"{agent.provider_id}/{agent.model_id}" if agent.provider_id and agent.model_id else "",
        "modelOverridden": model_overridden,
        "profileId": profile_id,
        "runtime": "adapter",
        "usage": result.get("usage", {}),
    }
