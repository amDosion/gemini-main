"""
统一模式路由

所有非聊天模式都通过此路由处理。
路由层只负责：
1. 接收请求
2. 参数验证
3. 用户认证（使用 Depends）
4. 获取凭证
5. 创建提供商服务（ProviderFactory）
6. 根据 mode 调用服务方法
7. 返回响应

不包含任何业务逻辑，业务逻辑在服务层。
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...core.credential_manager import get_provider_credentials
from ...core.mode_method_mapper import get_service_method, is_streaming_mode, is_image_edit_mode
from ...core.mode_method_mapper import get_mode_catalog
from ...core.provider_param_whitelist import (
    ProviderParamValidationError,
    validate_mode_param_keys,
)
from ...services.common.provider_factory import ProviderFactory
from ...services.common.attachment_service import AttachmentService
from ...services.common.mode_controls_catalog import validate_params_with_catalog
from ...services.common.model_capabilities import build_provider_mode_capabilities
from ...services.common.video_mode_contract import (
    merge_video_mode_attachment_params,
    normalize_video_generation_request_params,
    resolve_runtime_mode_controls_schema,
)
from ...utils.sse import build_safe_error_chunk, create_sse_response, encode_sse_data

# Get logger - it will propagate to root logger which has handler configured
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Ensure propagation is enabled (default is True, but make it explicit)
logger.propagate = True

router = APIRouter(prefix="/api/modes", tags=["modes"])
# ==================== Request/Response Models ====================

class Attachment(BaseModel):
    """
    Attachment model (images, files, etc.)

    注意：字段名使用 snake_case，因为 CaseConversionMiddleware 会自动
    将前端的 camelCase 转换为 snake_case。
    """
    id: Optional[str] = None
    mime_type: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None
    temp_url: Optional[str] = None
    file_uri: Optional[str] = None
    base64_data: Optional[str] = None
    role: Optional[str] = None  # 'mask' for mask images, etc.


class ModeOptions(BaseModel):
    """
    Mode options - flexible dict-like structure

    注意：字段名使用 snake_case，因为 CaseConversionMiddleware 会自动
    将前端的 camelCase 转换为 snake_case。
    """
    # 基础选项
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    enable_search: Optional[bool] = None
    enable_thinking: Optional[bool] = None
    voice: Optional[str] = None
    base_steps: Optional[int] = None
    mask_mode: Optional[str] = None
    duration_seconds: Optional[int] = None
    video_extension_count: Optional[int] = None
    storyboard_shot_seconds: Optional[int] = None
    generate_audio: Optional[bool] = None
    person_generation: Optional[str] = None
    subtitle_mode: Optional[str] = None
    subtitle_language: Optional[str] = None
    subtitle_script: Optional[str] = None
    storyboard_prompt: Optional[str] = None
    tracked_feature: Optional[str] = None
    tracking_overlay_text: Optional[str] = None
    source_video: Optional[Any] = None
    source_image: Optional[Any] = None
    last_frame_image: Optional[Any] = None
    video_mask_image: Optional[Any] = None
    video_mask_mode: Optional[str] = None
    provider_file_name: Optional[str] = None
    provider_file_uri: Optional[str] = None
    gcs_uri: Optional[str] = None
    delete_target: Optional[str] = None
    # Image generation options
    size: Optional[str] = None
    quality: Optional[str] = None
    style: Optional[str] = None
    resolution: Optional[str] = None
    seconds: Optional[str] = None
    number_of_images: Optional[int] = None
    aspect_ratio: Optional[str] = None
    image_aspect_ratio: Optional[str] = None
    image_resolution: Optional[str] = None
    image_style: Optional[str] = None
    # Image editing options
    edit_mode: Optional[str] = None
    frontend_session_id: Optional[str] = None
    session_id: Optional[str] = None  # Alias for frontend_session_id
    message_id: Optional[str] = None  # 消息ID（用于附件关联）
    # Edit模式新增字段
    active_image_url: Optional[str] = None  # CONTINUITY LOGIC用
    # Other options
    negative_prompt: Optional[str] = None
    guidance_scale: Optional[float] = None
    mask_dilation: Optional[float] = None  # Mask 编辑特有参数：掩码膨胀系数 (0.0-1.0)
    seed: Optional[int] = None
    # Google Imagen 高级参数
    output_mime_type: Optional[str] = None
    output_compression_quality: Optional[int] = None
    enhance_prompt: Optional[bool] = None
    enhance_prompt_model: Optional[str] = None
    # TongYi 专用参数
    prompt_extend: Optional[bool] = None  # AI 增强提示词
    add_magic_suffix: Optional[bool] = None  # 魔法词组
    # Outpainting 参数（image-outpainting 模式）
    outpaint_mode: Optional[str] = None  # 扩图模式：ratio | scale | offset | upscale
    x_scale: Optional[float] = None  # 水平缩放倍数 (scale 模式)
    y_scale: Optional[float] = None  # 垂直缩放倍数 (scale 模式)
    left_offset: Optional[int] = None  # 左侧偏移像素 (offset 模式)
    right_offset: Optional[int] = None  # 右侧偏移像素 (offset 模式)
    top_offset: Optional[int] = None  # 顶部偏移像素 (offset 模式)
    bottom_offset: Optional[int] = None  # 底部偏移像素 (offset 模式)
    output_ratio: Optional[str] = None  # 目标比例 (ratio 模式)
    upscale_factor: Optional[str] = None  # 放大倍数：x2 | x3 | x4 (upscale 模式)
    # Layered Design 参数
    layers: Optional[int] = None  # 图层分解数量 (2-10)
    canvas_w: Optional[int] = None  # 画布宽度
    canvas_h: Optional[int] = None  # 画布高度
    max_text_boxes: Optional[int] = None  # 最大文本框数量
    locale: Optional[str] = None  # 语言区域
    layer_doc: Optional[Dict[str, Any]] = None  # LayerDoc 渲染用
    simplify_tolerance: Optional[float] = None  # 矢量化简化容差
    smooth_iterations: Optional[int] = None  # 平滑迭代次数
    use_bezier: Optional[bool] = None  # 使用贝塞尔曲线
    bezier_smoothness: Optional[float] = None  # 贝塞尔平滑度
    threshold: Optional[int] = None  # 二值化阈值
    blur_radius: Optional[float] = None  # 模糊半径
    # Allow additional fields
    model_config = ConfigDict(extra="allow")


class ModeRequest(BaseModel):
    """
    统一模式请求

    注意：字段名使用 snake_case，因为 CaseConversionMiddleware 会自动
    将前端的 camelCase 转换为 snake_case。
    """
    model_id: str
    prompt: str
    attachments: Optional[List[Attachment]] = None
    options: Optional[ModeOptions] = None
    api_key: Optional[str] = None  # Optional, will try to get from database
    extra: Optional[Dict[str, Any]] = None  # Additional parameters


class ModeResponse(BaseModel):
    """统一模式响应"""
    success: bool
    data: Any
    provider: str
    mode: str
    error: Optional[str] = None


# ==================== Helper Functions ====================

def convert_attachments_to_reference_images(attachments: Optional[List[Attachment]]) -> Dict[str, Any]:
    """
    将 attachments 转换为 reference_images 字典格式
    
    Args:
        attachments: 附件列表
        
    Returns:
        reference_images 字典，格式：
        - 如果只有 URL：{'raw': 'data:image/png;base64,...'}
        - 如果有 attachment_id：{'raw': {'url': 'data:image/png;base64,...', 'attachment_id': 'xxx', 'mimeType': 'image/png'}}
    """
    if not attachments:
        return {}
    
    reference_images = {}
    for attachment in attachments:
        # 获取图片数据（优先级：url > temp_url > file_uri > base64_data）
        image_data = None
        if attachment.url:
            image_data = attachment.url
        elif attachment.temp_url:
            image_data = attachment.temp_url
        elif attachment.file_uri:
            image_data = attachment.file_uri
        elif attachment.base64_data:
            image_data = attachment.base64_data

        # 兼容仅传 attachment.id 的场景：
        # 先保留 attachment_id，后续可由数据库回填 URL。
        if attachment.id:
            ref_data = {
                'attachment_id': attachment.id,
                'mime_type': attachment.mime_type or 'image/png'
            }
            if image_data:
                ref_data['url'] = image_data
        else:
            if not image_data:
                continue
            ref_data = image_data  # 向后兼容：只传递 URL 字符串
        
        # 根据 role 设置键名
        if attachment.role == 'mask':
            reference_images['mask'] = ref_data
        else:
            # 默认作为 raw 图片（如果还没有 raw）
            if 'raw' not in reference_images:
                reference_images['raw'] = ref_data
            else:
                # 如果有多个非 mask 图片，使用列表或追加
                if isinstance(reference_images.get('raw'), list):
                    reference_images['raw'].append(ref_data)
                else:
                    reference_images['raw'] = [reference_images['raw'], ref_data]
    
    return reference_images
def _build_mode_error_detail(
    code: str,
    message: str,
    *,
    details: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "retryable": retryable,
    }


def _resolve_video_generation_error_status_code(error: Exception) -> int:
    if isinstance(error, ValueError):
        return 400

    lowered = str(error or "").lower()
    if (
        "resource_exhausted" in lowered
        or "exceeded your current quota" in lowered
        or "rate limit" in lowered
        or "quota" in lowered
    ):
        return 429

    return 500


def _build_stream_error_done_chunk() -> Dict[str, Any]:
    return {
        "content": "",
        "text": "",
        "chunk_type": "done",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "finish_reason": "error",
    }


def _resolve_mode_attachment_url(attachment: Attachment) -> str:
    for candidate in (
        attachment.url,
        attachment.temp_url,
        attachment.file_uri,
        attachment.base64_data,
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return ""


def _merge_multi_agent_attachment_inputs(
    workflow_input: Dict[str, Any],
    attachments: Optional[List[Attachment]],
) -> Dict[str, Any]:
    if not attachments:
        return workflow_input

    merged_input = dict(workflow_input)

    def merge_urls(list_key: str, single_key: str, values: List[str]) -> None:
        if not values:
            return
        existing_values: List[str] = []
        existing_raw = merged_input.get(list_key)
        if isinstance(existing_raw, list):
            existing_values = [str(item).strip() for item in existing_raw if str(item).strip()]
        single_raw = str(merged_input.get(single_key) or "").strip()
        if single_raw:
            existing_values = [single_raw, *existing_values]

        deduped: List[str] = []
        seen: set[str] = set()
        for item in [*values, *existing_values]:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)

        if deduped:
            merged_input[list_key] = deduped
            merged_input[single_key] = deduped[0]

    image_urls: List[str] = []
    file_urls: List[str] = []
    audio_urls: List[str] = []
    video_urls: List[str] = []

    for attachment in attachments:
        resource_url = _resolve_mode_attachment_url(attachment)
        if not resource_url:
            continue
        mime_type = str(attachment.mime_type or "").strip().lower()
        if mime_type.startswith("image/"):
            image_urls.append(resource_url)
            continue
        if mime_type.startswith("audio/"):
            audio_urls.append(resource_url)
            continue
        if mime_type.startswith("video/"):
            video_urls.append(resource_url)
            continue
        file_urls.append(resource_url)

    merge_urls("imageUrls", "imageUrl", image_urls)
    merge_urls("fileUrls", "fileUrl", file_urls)
    merge_urls("audioUrls", "audioUrl", audio_urls)
    merge_urls("videoUrls", "videoUrl", video_urls)
    return merged_input


def _build_multi_agent_meta_payload(
    raw_meta: Any,
    *,
    request_body: ModeRequest,
    provider: str,
    mode: str,
) -> Dict[str, Any]:
    if not isinstance(raw_meta, dict):
        meta_payload: Dict[str, Any] = {}
    else:
        meta_payload = dict(raw_meta)

    meta_payload.setdefault("source", "provider-mode")
    meta_payload.setdefault("requestedProvider", provider)
    meta_payload.setdefault("requestedMode", mode)
    meta_payload.setdefault("modeProviderId", provider)
    if str(request_body.model_id or "").strip():
        meta_payload.setdefault("modeModelId", str(request_body.model_id).strip())
    return meta_payload


def _build_inline_multi_agent_node(
    *,
    node_id: str,
    label: str,
    description: str,
    provider: str,
    model_id: str,
    system_prompt: str,
    icon: str,
    icon_color: str,
    x: int,
    y: int,
    task_type: str = "chat",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    input_mapping: str = "",
    extra_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "type": "agent",
        "label": label,
        "description": description,
        "icon": icon,
        "iconColor": icon_color,
        "inlineProviderId": provider,
        "inlineModelId": model_id,
        "inlineAgentName": label,
        "inlineSystemPrompt": system_prompt,
        "agentTaskType": task_type,
    }
    if temperature is not None:
        data["agentTemperature"] = temperature
    if max_tokens is not None:
        data["agentMaxTokens"] = max_tokens
    if input_mapping.strip():
        data["inputMapping"] = input_mapping
    if isinstance(extra_data, dict):
        data.update(extra_data)

    return {
        "id": node_id,
        "type": "agent",
        "position": {"x": x, "y": y},
        "data": data,
    }


def _build_default_multi_agent_workflow_payload(
    *,
    request_body: ModeRequest,
    provider: str,
    mode: str,
    raw_input: Any,
    raw_meta: Any,
    raw_async_mode: Any,
) -> Dict[str, Any]:
    workflow_input = dict(raw_input) if isinstance(raw_input, dict) else {}
    workflow_input = _merge_multi_agent_attachment_inputs(workflow_input, request_body.attachments)

    prompt_text = str(request_body.prompt or "").strip()
    if prompt_text and not str(
        workflow_input.get("task")
        or workflow_input.get("prompt")
        or workflow_input.get("text")
        or ""
    ).strip():
        workflow_input["task"] = prompt_text

    model_id = str(request_body.model_id or "").strip() or "workflow-runtime"
    meta_payload = _build_multi_agent_meta_payload(
        raw_meta,
        request_body=request_body,
        provider=provider,
        mode=mode,
    )
    meta_payload.setdefault("workflowKind", "default-inline-multi-agent")

    base_max_tokens = getattr(request_body.options, "max_tokens", None) if request_body.options else None

    nodes: List[Dict[str, Any]] = [
        {
            "id": "start-mode-runtime",
            "type": "start",
            "position": {"x": 80, "y": 220},
            "data": {
                "type": "start",
                "label": "开始",
                "description": "接收多智能体模式输入",
                "icon": "🚀",
                "iconColor": "bg-blue-500",
            },
        }
    ]
    edges: List[Dict[str, Any]] = []

    has_image_input = bool(workflow_input.get("imageUrl") or workflow_input.get("imageUrls"))
    has_file_input = bool(workflow_input.get("fileUrl") or workflow_input.get("fileUrls"))

    if has_image_input:
        nodes.extend(
            [
                {
                    "id": "input-image-mode-runtime",
                    "type": "input_image",
                    "position": {"x": 300, "y": 220},
                    "data": {
                        "type": "input_image",
                        "label": "图片输入",
                        "description": "接收用户图片上下文",
                        "icon": "🖼️",
                        "iconColor": "bg-lime-500",
                    },
                },
                _build_inline_multi_agent_node(
                    node_id="vision-observer-mode-runtime",
                    label="视觉观察员",
                    description="先提取图片中的事实与约束",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的视觉观察员。"
                        "先严格依据图片事实提取主体、场景、限制条件与不确定项，"
                        "不要直接给最终建议。"
                    ),
                    icon="🧠",
                    icon_color="bg-indigo-500",
                    x=560,
                    y=220,
                    task_type="vision-understand",
                    temperature=0.2,
                    max_tokens=base_max_tokens,
                    input_mapping="用户任务：{{input.task}}",
                    extra_data={"agentReferenceImageUrl": "{{input.imageUrl}}"},
                ),
                _build_inline_multi_agent_node(
                    node_id="analysis-mode-runtime",
                    label="分析策划师",
                    description="结合图片事实与任务要求给出方案",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的分析策划师。"
                        "必须基于视觉观察结果和用户任务，提出结构化方案、关键假设与执行步骤。"
                    ),
                    icon="🧭",
                    icon_color="bg-teal-500",
                    x=820,
                    y=220,
                    task_type="chat",
                    temperature=0.45,
                    max_tokens=base_max_tokens,
                    input_mapping=(
                        "用户任务：{{input.task}}\n\n"
                        "视觉观察结果：{{vision-observer-mode-runtime.output.text}}"
                    ),
                ),
                _build_inline_multi_agent_node(
                    node_id="review-mode-runtime",
                    label="结果审校员",
                    description="合并结论并输出最终答复",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的结果审校员。"
                        "负责校对事实与推断，压缩重复内容，输出最终可执行结论。"
                    ),
                    icon="✅",
                    icon_color="bg-emerald-500",
                    x=1080,
                    y=220,
                    task_type="chat",
                    temperature=0.3,
                    max_tokens=base_max_tokens,
                    input_mapping=(
                        "用户任务：{{input.task}}\n\n"
                        "视觉观察：{{vision-observer-mode-runtime.output.text}}\n\n"
                        "分析方案：{{analysis-mode-runtime.output.text}}"
                    ),
                ),
                {
                    "id": "end-mode-runtime",
                    "type": "end",
                    "position": {"x": 1340, "y": 220},
                    "data": {
                        "type": "end",
                        "label": "结束",
                        "description": "输出最终结果",
                        "icon": "🏁",
                        "iconColor": "bg-green-500",
                    },
                },
            ]
        )
        edges.extend(
            [
                {"id": "edge-mode-runtime-1", "source": "start-mode-runtime", "target": "input-image-mode-runtime"},
                {"id": "edge-mode-runtime-2", "source": "input-image-mode-runtime", "target": "vision-observer-mode-runtime"},
                {"id": "edge-mode-runtime-3", "source": "vision-observer-mode-runtime", "target": "analysis-mode-runtime"},
                {"id": "edge-mode-runtime-4", "source": "analysis-mode-runtime", "target": "review-mode-runtime"},
                {"id": "edge-mode-runtime-5", "source": "review-mode-runtime", "target": "end-mode-runtime"},
            ]
        )
    elif has_file_input:
        nodes.extend(
            [
                {
                    "id": "input-file-mode-runtime",
                    "type": "input_file",
                    "position": {"x": 300, "y": 220},
                    "data": {
                        "type": "input_file",
                        "label": "文件输入",
                        "description": "接收用户文件上下文",
                        "icon": "📎",
                        "iconColor": "bg-cyan-500",
                    },
                },
                _build_inline_multi_agent_node(
                    node_id="analysis-mode-runtime",
                    label="数据分析师",
                    description="先提取文件中的关键结构与洞察",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的数据分析师。"
                        "先理解文件结构，提取关键趋势、异常和结论，再给出解释。"
                    ),
                    icon="📊",
                    icon_color="bg-sky-500",
                    x=560,
                    y=220,
                    task_type="data-analysis",
                    temperature=0.25,
                    max_tokens=base_max_tokens,
                    input_mapping="用户任务：{{input.task}}\n\n文件地址：{{input.fileUrl}}",
                    extra_data={"agentFileUrl": "{{input.fileUrl}}"},
                ),
                _build_inline_multi_agent_node(
                    node_id="review-mode-runtime",
                    label="结果审校员",
                    description="合并分析结论并给出最终建议",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的结果审校员。"
                        "将数据分析结果整理为可执行结论，标明事实、推断和后续动作。"
                    ),
                    icon="✅",
                    icon_color="bg-emerald-500",
                    x=820,
                    y=220,
                    task_type="chat",
                    temperature=0.3,
                    max_tokens=base_max_tokens,
                    input_mapping=(
                        "用户任务：{{input.task}}\n\n"
                        "数据分析结果：{{analysis-mode-runtime.output.text}}"
                    ),
                ),
                {
                    "id": "end-mode-runtime",
                    "type": "end",
                    "position": {"x": 1080, "y": 220},
                    "data": {
                        "type": "end",
                        "label": "结束",
                        "description": "输出最终结果",
                        "icon": "🏁",
                        "iconColor": "bg-green-500",
                    },
                },
            ]
        )
        edges.extend(
            [
                {"id": "edge-mode-runtime-1", "source": "start-mode-runtime", "target": "input-file-mode-runtime"},
                {"id": "edge-mode-runtime-2", "source": "input-file-mode-runtime", "target": "analysis-mode-runtime"},
                {"id": "edge-mode-runtime-3", "source": "analysis-mode-runtime", "target": "review-mode-runtime"},
                {"id": "edge-mode-runtime-4", "source": "review-mode-runtime", "target": "end-mode-runtime"},
            ]
        )
    else:
        nodes.extend(
            [
                _build_inline_multi_agent_node(
                    node_id="planner-mode-runtime",
                    label="任务规划师",
                    description="拆解任务，定义分析路径和检查点",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的任务规划师。"
                        "先拆解目标、约束、关键问题和执行顺序，不直接给最终答案。"
                    ),
                    icon="🗺️",
                    icon_color="bg-violet-500",
                    x=320,
                    y=220,
                    task_type="chat",
                    temperature=0.35,
                    max_tokens=base_max_tokens,
                ),
                _build_inline_multi_agent_node(
                    node_id="analysis-mode-runtime",
                    label="执行专家",
                    description="按规划展开分析并形成主体方案",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的执行专家。"
                        "基于任务规划做深入分析，给出结构化主体答案与关键依据。"
                    ),
                    icon="🛠️",
                    icon_color="bg-teal-500",
                    x=620,
                    y=220,
                    task_type="chat",
                    temperature=0.45,
                    max_tokens=base_max_tokens,
                    input_mapping=(
                        "用户任务：{{input.task}}\n\n"
                        "任务规划：{{planner-mode-runtime.output.text}}"
                    ),
                ),
                _build_inline_multi_agent_node(
                    node_id="review-mode-runtime",
                    label="结果审校员",
                    description="校验结论、补齐风险并整理最终输出",
                    provider=provider,
                    model_id=model_id,
                    system_prompt=(
                        "你是多智能体链路中的结果审校员。"
                        "负责检查遗漏、标注风险，整理成最终答复。"
                    ),
                    icon="✅",
                    icon_color="bg-emerald-500",
                    x=920,
                    y=220,
                    task_type="chat",
                    temperature=0.25,
                    max_tokens=base_max_tokens,
                    input_mapping=(
                        "用户任务：{{input.task}}\n\n"
                        "任务规划：{{planner-mode-runtime.output.text}}\n\n"
                        "主体分析：{{analysis-mode-runtime.output.text}}"
                    ),
                ),
                {
                    "id": "end-mode-runtime",
                    "type": "end",
                    "position": {"x": 1220, "y": 220},
                    "data": {
                        "type": "end",
                        "label": "结束",
                        "description": "输出最终结果",
                        "icon": "🏁",
                        "iconColor": "bg-green-500",
                    },
                },
            ]
        )
        edges.extend(
            [
                {"id": "edge-mode-runtime-1", "source": "start-mode-runtime", "target": "planner-mode-runtime"},
                {"id": "edge-mode-runtime-2", "source": "planner-mode-runtime", "target": "analysis-mode-runtime"},
                {"id": "edge-mode-runtime-3", "source": "analysis-mode-runtime", "target": "review-mode-runtime"},
                {"id": "edge-mode-runtime-4", "source": "review-mode-runtime", "target": "end-mode-runtime"},
            ]
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "input": workflow_input,
        "meta": meta_payload,
        "async_mode": bool(raw_async_mode),
    }


def _coerce_multi_agent_workflow_payload(
    request_body: ModeRequest,
    *,
    provider: str,
    mode: str,
) -> Dict[str, Any]:
    raw_extra = request_body.extra if isinstance(request_body.extra, dict) else {}
    has_explicit_workflow = isinstance(raw_extra.get("workflow"), dict) or any(
        key in raw_extra for key in ("workflow", "nodes", "edges")
    )
    workflow_payload = raw_extra.get("workflow")
    if not isinstance(workflow_payload, dict):
        workflow_payload = raw_extra

    if not has_explicit_workflow:
        return _build_default_multi_agent_workflow_payload(
            request_body=request_body,
            provider=provider,
            mode=mode,
            raw_input=raw_extra.get("input"),
            raw_meta=raw_extra.get("meta"),
            raw_async_mode=raw_extra.get("async_mode", raw_extra.get("asyncMode")),
        )

    if not isinstance(workflow_payload, dict):
        raise ValueError("multi-agent mode requires extra.workflow payload")

    nodes = workflow_payload.get("nodes")
    edges = workflow_payload.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("multi-agent workflow payload must include nodes[] and edges[]")

    workflow_input = workflow_payload.get("input")
    if not isinstance(workflow_input, dict):
        workflow_input = {}
    else:
        workflow_input = dict(workflow_input)

    workflow_input = _merge_multi_agent_attachment_inputs(workflow_input, request_body.attachments)

    prompt_text = str(request_body.prompt or "").strip()
    if prompt_text and not str(
        workflow_input.get("task")
        or workflow_input.get("prompt")
        or workflow_input.get("text")
        or ""
    ).strip():
        workflow_input["task"] = prompt_text

    meta_payload = _build_multi_agent_meta_payload(
        workflow_payload.get("meta"),
        request_body=request_body,
        provider=provider,
        mode=mode,
    )

    async_mode_raw = workflow_payload.get("async_mode")
    if async_mode_raw is None:
        async_mode_raw = workflow_payload.get("asyncMode")

    return {
        "nodes": nodes,
        "edges": edges,
        "input": workflow_input,
        "meta": meta_payload,
        "async_mode": bool(async_mode_raw),
    }


async def _execute_multi_agent_mode(
    *,
    provider: str,
    mode: str,
    request_body: ModeRequest,
    request: Request,
    user_id: str,
    db: Session,
) -> Dict[str, Any]:
    from ..ai.workflows import WorkflowExecuteRequest, execute_workflow

    workflow_payload = _coerce_multi_agent_workflow_payload(
        request_body,
        provider=provider,
        mode=mode,
    )
    workflow_request = WorkflowExecuteRequest(
        nodes=workflow_payload["nodes"],
        edges=workflow_payload["edges"],
        input=workflow_payload["input"],
        meta=workflow_payload["meta"],
        async_mode=workflow_payload["async_mode"],
    )
    result = await execute_workflow(
        request=workflow_request,
        raw_request=request,
        user_id=user_id,
        db=db,
    )
    return result if isinstance(result, dict) else {"status": "completed", "result": result}


# ==================== API Endpoints ====================

@router.get("/{provider}/{mode}/controls")
async def get_mode_controls_schema(
    provider: str,
    mode: str,
    model_id: Optional[str] = Query(None, description="Optional model id for model-specific overrides"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    Return provider+mode control schema from single-source catalog.
    """
    try:
        schema = resolve_runtime_mode_controls_schema(
            provider=provider,
            mode=mode,
            model_id=model_id,
            user_id=user_id,
            db=db,
        )
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"Controls schema not found for provider={provider}, mode={mode}"
            )

        return {
            "success": True,
            "provider": provider,
            "mode": mode,
            "model_id": model_id,
            "schema": schema,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[Modes] Failed to resolve controls schema: provider={provider}, mode={mode}, model_id={model_id}, error={e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to resolve controls schema: {str(e)}")


@router.get("/{provider}/capabilities")
async def get_provider_mode_capabilities(
    provider: str,
    include_internal: bool = Query(False, description="Include internal (non-navigation) modes"),
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
):
    """
    Runtime mode capability probe for a provider.

    Returns provider+mode runtime executability derived from backend runtime checks.
    """
    try:
        mode_catalog = get_mode_catalog(include_internal=include_internal)
        snapshot = build_provider_mode_capabilities(
            provider=provider,
            db=db,
            user_id=user_id,
            mode_catalog=mode_catalog,
            include_internal=include_internal,
        )

        ordered = []
        mode_map = snapshot.get("modes", {}) if isinstance(snapshot, dict) else {}
        if isinstance(mode_map, dict):
            for item in mode_catalog:
                mode_id = str(item.get("id") or "")
                if not mode_id:
                    continue
                capability = mode_map.get(mode_id, {})
                ordered.append({
                    "id": mode_id,
                    "label": item.get("label"),
                    "group": item.get("group"),
                    "visible_in_navigation": bool(item.get("visible_in_navigation", True)),
                    "service_method": item.get("service_method"),
                    "runtime_enabled": bool(capability.get("runtime_enabled", True)),
                    "reason_code": capability.get("reason_code"),
                    "reason": capability.get("reason"),
                    "required_api_mode": capability.get("required_api_mode"),
                })

        return {
            "success": True,
            "provider": provider,
            "normalized_provider": snapshot.get("normalized_provider"),
            "api_mode": snapshot.get("api_mode"),
            "vertex_ready": snapshot.get("vertex_ready"),
            "capabilities": ordered,
        }
    except Exception as e:
        logger.error(
            f"[Modes] Failed to probe mode capabilities: provider={provider}, include_internal={include_internal}, error={e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to probe mode capabilities: {str(e)}")

@router.post("/{provider}/{mode}")
async def handle_mode(
    provider: str,
    mode: str,
    request_body: ModeRequest,
    request: Request,
    user_id: str = Depends(require_current_user),  # ✅ 自动注入 user_id
    db: Session = Depends(get_db)
):
    """
    统一的模式处理端点

    根据 provider 和 mode 参数，直接调用提供商服务的对应方法。
    服务内部会根据 mode 分发到子服务。

    Args:
        provider: 提供商名称 (google, tongyi, openai, etc.)
        mode: 模式名称 (image-gen, image-edit, video-gen, etc.)
        request_body: 请求体
        request: FastAPI 请求对象
        user_id: 用户 ID（自动注入）
        db: 数据库会话

    Returns:
        ModeResponse: 统一的响应格式
    """
    import time
    import sys
    
    # ✅ 立即输出日志，确保能看到请求到达（使用多种方式确保输出）
    request_start_time = time.time()
    logger.info(f"[Modes] ========== 开始处理模式请求 ==========")
    logger.info(f"[Modes] 📥 请求到达: {provider}/{mode}")
    # 同时使用 print 作为备用（确保能看到输出）
    
    try:
        # ✅ 记录 token 来源（用于诊断 user_id 不一致问题）
        auth_header = request.headers.get("Authorization")
        cookie_token = request.cookies.get("access_token")
        token_source = "未知"
        if auth_header:
            token_source = "Authorization header"
        elif cookie_token:
            token_source = "Cookie (access_token)"
        else:
            token_source = "无 token"
        
        logger.info(f"[Modes] 📥 请求信息:")
        logger.debug(f"[Modes]     - provider: {provider}")
        logger.debug(f"[Modes]     - mode: {mode}")
        logger.debug(f"[Modes]     - user_id: {user_id}")  # ✅ 不截断 ID，显示完整 ID
        logger.debug(f"[Modes]     - token来源: {token_source}")
        logger.debug(f"[Modes]     - 有Authorization header: {'是' if auth_header else '否'}")
        logger.debug(f"[Modes]     - 有Cookie token: {'是' if cookie_token else '否'}")
        logger.debug(f"[Modes]     - model_id: {request_body.model_id}")
        logger.debug(f"[Modes]     - prompt长度: {len(request_body.prompt)}")
        logger.debug(f"[Modes]     - attachments数量: {len(request_body.attachments) if request_body.attachments else 0}")

        option_keys = set(request_body.options.model_dump(exclude_none=True).keys()) if request_body.options else set()
        extra_keys = set(request_body.extra.keys()) if request_body.extra else set()
        validate_mode_param_keys(
            provider=provider,
            mode=mode,
            option_keys=option_keys,
            extra_keys=extra_keys,
        )

        # ✅ 1. 根据 mode 获取服务方法名
        logger.info(f"[Modes] 🔄 [步骤1] 获取服务方法名...")
        method_name = get_service_method(mode)
        if not method_name:
            logger.error(f"[Modes] ❌ [步骤1] 不支持的模式: {mode}")
            raise ValueError(f"Unsupported mode: {mode}")
        logger.info(f"[Modes] ✅ [步骤1] 方法名: {method_name}")

        if method_name == "multi_agent":
            logger.info(f"[Modes] 🔄 [步骤2] multi-agent 模式委托到通用 workflow runtime")
            result = await _execute_multi_agent_mode(
                provider=provider,
                mode=mode,
                request_body=request_body,
                request=request,
                user_id=user_id,
                db=db,
            )
            total_time = (time.time() - request_start_time) * 1000
            logger.info(f"[Modes] ========== 模式请求处理完成 (总耗时: {total_time:.2f}ms) ==========")
            logger.debug(f"[Modes]     - provider: {provider}")
            logger.debug(f"[Modes]     - mode: {mode}")
            logger.debug(f"[Modes]     - 成功: True")
            return ModeResponse(
                success=True,
                data=result,
                provider=provider,
                mode=mode,
            )

        # 2. 获取凭证
        logger.info(f"[Modes] 🔄 [步骤2] 获取提供商凭证...")
        credential_start = time.time()
        api_key, api_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request_body.api_key,
            request_base_url=request_body.options.base_url if request_body.options else None
        )
        credential_time = (time.time() - credential_start) * 1000
        logger.info(f"[Modes] ✅ [步骤2] 凭证获取完成 (耗时: {credential_time:.2f}ms)")
        logger.debug(f"[Modes]     - api_key: {'已设置' if api_key else 'None'}")
        logger.debug(f"[Modes]     - api_url: {api_url[:80] + '...' if api_url and len(api_url) > 80 else api_url or 'None'}")

        # ✅ 3. 创建提供商服务（如 GoogleService）
        logger.info(f"[Modes] 🔄 [步骤3] 创建提供商服务...")
        service_start = time.time()
        service = ProviderFactory.create(
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            user_id=user_id,
            db=db
        )
        service_time = (time.time() - service_start) * 1000
        service_type = type(service).__name__
        logger.info(f"[Modes] ✅ [步骤3] 服务创建完成 (耗时: {service_time:.2f}ms)")
        logger.debug(f"[Modes]     - service类型: {service_type}")

        # ✅ 4. 检查服务是否支持该方法
        logger.info(f"[Modes] 🔄 [步骤4] 检查服务是否支持方法...")
        if not hasattr(service, method_name):
            logger.error(f"[Modes] ❌ [步骤4] 服务不支持方法: {service_type}.{method_name}")
            raise ValueError(f"Provider '{provider}' does not support method '{method_name}' for mode '{mode}'")
        logger.info(f"[Modes] ✅ [步骤4] 服务支持方法: {service_type}.{method_name}")

        # ✅ 5. 准备参数
        logger.info(f"[Modes] 🔄 [步骤5] 准备调用参数...")
        param_start = time.time()
        method = getattr(service, method_name)
        
        # 构建调用参数
        params = {
            "model": request_body.model_id,
            "prompt": request_body.prompt,
        }
        logger.debug(f"[Modes]     - 基础参数已设置: model={params['model']}, prompt长度={len(params['prompt'])}")
        
        # **特殊处理**：根据方法类型调整参数
        # - generate_speech 需要 text 和 voice 参数
        if method_name == "generate_speech":
            params["text"] = request_body.prompt
            # 从 options 中获取 voice，如果没有则使用默认值
            if request_body.options and hasattr(request_body.options, "voice") and request_body.options.voice:
                params["voice"] = request_body.options.voice
            else:
                params["voice"] = "alloy"  # 默认语音
        
        # 添加 options 中的参数
        if request_body.options:
            options_dict = request_body.options.model_dump(exclude_none=True)
            # 对于 generate_speech，voice 已经在上面处理，避免重复
            if method_name == "generate_speech" and "voice" in options_dict:
                options_dict.pop("voice", None)
            params.update(options_dict)
            logger.debug(f"[Modes]     - 已添加 options 参数: {len(options_dict)} 个")
        
        # 添加 extra 参数
        if request_body.extra:
            params.update(request_body.extra)
            logger.debug(f"[Modes]     - 已添加 extra 参数: {len(request_body.extra)} 个")
        
        # **重要**：对于 edit_image 方法，需要传递 mode 参数
        # GoogleService.edit_image() 会根据 mode 参数智能分发到不同的子服务
        if method_name == "edit_image":
            # 将 URL 路径中的 mode 参数传递给 edit_image 方法
            params["mode"] = mode

        # **重要**：对于 layered_design 方法，需要传递 mode 参数
        # GoogleService.layered_design() 会根据 mode 参数智能分发到不同的子方法
        if method_name == "layered_design":
            # 将 URL 路径中的 mode 参数传递给 layered_design 方法
            params["mode"] = mode
            logger.debug(f"[Modes]     - layered_design mode: {mode}")

        # **重要**：对于 expand_image 方法，需要将 outpaint_mode 映射为 mode
        # ExpandService.expand_image() 期望的参数名是 "mode" 而非 "outpaint_mode"
        # 注意：camelCase → snake_case 转换由 CaseConversionMiddleware 自动完成
        if method_name == "expand_image":
            # outpaint_mode → mode (语义映射，中间件已将 outpaintMode 转换为 outpaint_mode)
            if "outpaint_mode" in params:
                params["mode"] = params.pop("outpaint_mode")
                logger.debug(f"[Modes]     - expand_image mode: {params['mode']}")

        # **新增**：处理 Edit 模式的 CONTINUITY LOGIC
        # 如果提供了 active_image_url，使用 AttachmentService 解析
        if method_name == "edit_image" and request_body.options and request_body.options.active_image_url:
            import time
            continuity_start_time = time.time()

            logger.info(f"[Modes] ========== 开始处理Edit模式的CONTINUITY LOGIC ==========")
            logger.info(f"[Modes] 📥 CONTINUITY参数:")
            logger.debug(f"[Modes]     - method_name: {method_name}")
            url_type = 'Blob' if request_body.options.active_image_url.startswith('blob:') else 'Base64' if request_body.options.active_image_url.startswith('data:') else 'HTTP' if request_body.options.active_image_url.startswith('http') else '未知'
            logger.debug(f"[Modes]     - active_image_url类型: {url_type}")
            logger.debug(f"[Modes]     - active_image_url长度: {len(request_body.options.active_image_url)}")

            attachment_service = AttachmentService(db)

            # 获取会话ID和消息列表
            session_id = request_body.options.frontend_session_id or request_body.options.session_id
            if session_id:
                logger.info(f"[Modes] 🔍 获取会话ID和消息列表...")
                logger.debug(f"[Modes]     - session_id: {session_id}")  # ✅ 不截断 ID，显示完整 ID
                
                # 从 extra 中获取 messages，如果为空则从数据库查询
                messages = []
                if request_body.extra and "messages" in request_body.extra:
                    messages = request_body.extra["messages"]
                    logger.debug(f"[Modes]     - 从 extra 中获取 messages: {len(messages)} 条")
                elif session_id:
                    # 从数据库查询会话的所有消息（用于CONTINUITY LOGIC查找附件）
                    logger.debug(f"[Modes]     - 从数据库查询会话消息...")
                    from ...models.db_models import Message
                    db_messages = db.query(Message).filter_by(session_id=session_id).order_by(Message.timestamp.asc()).all()
                    messages = [msg.to_dict() for msg in db_messages if hasattr(msg, 'to_dict')]
                    logger.debug(f"[Modes]     - 从数据库查询到 {len(messages)} 条消息")
                
                # 解析 CONTINUITY 附件
                logger.info(f"[Modes] 🔄 调用 AttachmentService.resolve_continuity_attachment()...")
                resolved = await attachment_service.resolve_continuity_attachment(
                    active_image_url=request_body.options.active_image_url,
                    session_id=session_id,
                    user_id=user_id,
                    messages=messages
                )
                
                continuity_elapsed = (time.time() - continuity_start_time) * 1000
                
                if resolved:
                    # 将解析的附件添加到 reference_images
                    if "reference_images" not in params:
                        params["reference_images"] = {}
                    params["reference_images"]["raw"] = resolved["url"]
                    
                    has_cloud_url = resolved["status"] == "completed" and resolved["url"] and resolved["url"].startswith("http")
                    logger.info(f"[Modes] ✅ CONTINUITY附件解析成功 (耗时: {continuity_elapsed:.2f}ms):")
                    logger.debug(f"[Modes]     - attachment_id: {resolved['attachment_id']}")  # ✅ 不截断 ID，显示完整 ID
                    logger.debug(f"[Modes]     - status: {resolved['status']}")
                    logger.debug(f"[Modes]     - hasCloudUrl: {has_cloud_url}")
                    # ✅ 对于 BASE64 URL，只输出类型和长度，不输出完整内容
                    if resolved.get('url'):
                        if resolved['url'].startswith('data:'):
                            url_display = f"Base64 Data URL (长度: {len(resolved['url'])} 字符)"
                        else:
                            url_display = resolved['url'][:80] + '...' if len(resolved['url']) > 80 else resolved['url']
                    else:
                        url_display = 'None'
                    logger.debug(f"[Modes]     - url: {url_display}")
                    task_id_display = resolved.get('task_id') or 'None'  # ✅ 不截断 task_id，显示完整 ID
                    logger.debug(f"[Modes]     - taskId: {task_id_display}")
                    logger.debug(f"[Modes]     - 已添加到 reference_images.raw")
                    logger.info(f"[Modes] ========== CONTINUITY LOGIC处理完成 ==========")
                else:
                    logger.warning(f"[Modes] ⚠️ CONTINUITY附件解析失败 (耗时: {continuity_elapsed:.2f}ms): 未找到匹配的附件")
            else:
                logger.warning(f"[Modes] ⚠️ 跳过CONTINUITY LOGIC: 未提供 session_id")
        
        # **特殊处理**：对于需要文件数据的方法（pdf-extract, virtual-try-on, segment-clothing 等）
        # 从 attachments 中提取数据
        if request_body.attachments:
            logger.debug(f"[Modes]     - 处理 attachments: {len(request_body.attachments)} 个")
            if method_name in {"generate_video", "understand_video", "delete_video"}:
                params, video_params = merge_video_mode_attachment_params(
                    method_name=method_name,
                    params=params,
                    attachments=request_body.attachments,
                )
                if method_name == "generate_video":
                    if "source_video" in video_params:
                        logger.info("[Modes]     - video-gen: 已从附件注入 source_video")
                    if "source_image" in video_params:
                        logger.info("[Modes]     - video-gen: 已从附件注入 source_image")
                    if "video_mask_image" in video_params:
                        logger.info("[Modes]     - video-gen: 已从附件注入 video_mask_image")
                elif method_name == "understand_video" and "source_video" in video_params:
                    logger.info("[Modes]     - video-understand: 已从附件注入 source_video")
                elif method_name == "delete_video":
                    if any(params.get(key) for key in ("provider_file_name", "provider_file_uri", "gcs_uri")):
                        logger.info("[Modes]     - video-delete: 已从附件注入 provider 资产引用")
            else:
                reference_images = convert_attachments_to_reference_images(request_body.attachments)

                # ✅ 如果有 attachment_id，查找数据库中的附件信息
                if reference_images and 'raw' in reference_images:
                    raw_data = reference_images['raw']
                    if isinstance(raw_data, dict) and 'attachment_id' in raw_data:
                        attachment_id = raw_data['attachment_id']

                        # 从数据库查询附件信息
                        from ...models.db_models import MessageAttachment
                        db_attachment = db.query(MessageAttachment).filter_by(
                            id=attachment_id,
                            user_id=user_id
                        ).first()

                        if db_attachment:
                            logger.info(f"[Modes] ✅ 找到数据库中的附件: attachment_id={attachment_id}")  # ✅ 不截断 ID，显示完整 ID
                            logger.debug(f"[Modes]     - upload_status: {db_attachment.upload_status}")
                            logger.debug(f"[Modes]     - has_url: {bool(db_attachment.url)}")
                            logger.debug(f"[Modes]     - has_temp_url: {bool(db_attachment.temp_url)}")

                            # ✅ 如果已上传完成，优先使用 url（云端永久 URL）
                            if db_attachment.upload_status == 'completed' and db_attachment.url:
                                raw_data['url'] = db_attachment.url
                                # ✅ 对于 BASE64 URL，只输出类型和长度，不输出完整内容
                                if db_attachment.url.startswith('data:'):
                                    logger.debug(f"[Modes]     - 使用云存储 URL: Base64 Data URL (长度: {len(db_attachment.url)} 字符)")
                                else:
                                    logger.debug(f"[Modes]     - 使用云存储 URL: {db_attachment.url[:80] + '...' if len(db_attachment.url) > 80 else db_attachment.url}")
                            # ✅ 如果未上传完成，使用 temp_url（Base64）
                            elif db_attachment.temp_url:
                                raw_data['url'] = db_attachment.temp_url
                                # ✅ 对于 BASE64 URL，只输出类型和长度，不输出完整内容
                                if db_attachment.temp_url.startswith('data:'):
                                    logger.debug(f"[Modes]     - 使用临时 URL: Base64 Data URL (长度: {len(db_attachment.temp_url)} 字符)")
                                else:
                                    logger.debug(f"[Modes]     - 使用临时 URL: {db_attachment.temp_url[:80] + '...' if len(db_attachment.temp_url) > 80 else db_attachment.temp_url}")

                            # 更新 reference_images
                            reference_images['raw'] = raw_data
                        else:
                            logger.warning(f"[Modes] ⚠️ 未找到数据库中的附件: attachment_id={attachment_id}")  # ✅ 不截断 ID，显示完整 ID

                if reference_images:
                    params["reference_images"] = reference_images
                    logger.debug(f"[Modes]     - 已转换 reference_images: {len(reference_images)} 个")

            # 对于 segment-clothing，需要从 attachments 中提取图像数据
            if method_name == "segment_clothing":
                # 查找图像附件并添加到 reference_images
                for attachment in request_body.attachments:
                    if attachment.mime_type and "image" in attachment.mime_type.lower():
                        # 如果有 base64_data，直接使用
                        if attachment.base64_data:
                            image_data = attachment.base64_data
                            if image_data.startswith("data:"):
                                image_data = image_data.split(",", 1)[1]
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["raw"] = image_data
                        # 如果有 URL，需要下载（在服务层处理）
                        elif attachment.url or attachment.temp_url:
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["raw_url"] = attachment.url or attachment.temp_url
                        break
                # 从 extra 中获取 target_clothing
                if request_body.extra and "target_clothing" in request_body.extra:
                    params["target_clothing"] = request_body.extra["target_clothing"]

            # 对于 pdf-extract，需要从 attachments 中提取 PDF 数据
            if method_name == "extract_pdf_data":
                # 查找 PDF 附件
                for attachment in request_body.attachments:
                    if attachment.mime_type and "pdf" in attachment.mime_type.lower():
                        # 如果有 base64_data，直接使用
                        if attachment.base64_data:
                            import base64
                            # 移除 data URI 前缀（如果有）
                            pdf_data = attachment.base64_data
                            if pdf_data.startswith("data:"):
                                pdf_data = pdf_data.split(",", 1)[1]
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["pdf_bytes"] = base64.b64decode(pdf_data)
                        # 如果有 URL，需要下载（在服务层处理）
                        elif attachment.url or attachment.temp_url:
                            if "reference_images" not in params:
                                params["reference_images"] = {}
                            params["reference_images"]["pdf_url"] = attachment.url or attachment.temp_url
                        break
        
        # ✅ 统一参数校验：通过 mode_controls_catalog 单一源校验关键参数
        params = validate_params_with_catalog(
            provider=provider,
            mode=mode,
            model_id=request_body.model_id,
            params=params
        )

        if method_name == "generate_video":
            params, video_request_meta = normalize_video_generation_request_params(
                provider=provider,
                mode=mode,
                model_id=request_body.model_id,
                params=params,
                user_id=user_id,
                db=db,
            )
            if video_request_meta.get("input_strategy"):
                logger.info(
                    "[Modes]     - video-gen backend contract input_strategy: %s",
                    video_request_meta.get("input_strategy"),
                )
            if video_request_meta.get("runtime_api_mode"):
                logger.info(
                    "[Modes]     - video-gen backend contract runtime_api_mode: %s",
                    video_request_meta.get("runtime_api_mode"),
                )

        param_time = (time.time() - param_start) * 1000
        logger.info(f"[Modes] ✅ [步骤5] 参数准备完成 (耗时: {param_time:.2f}ms)")
        logger.debug(f"[Modes]     - 最终参数数量: {len(params)}")
        logger.debug(f"[Modes]     - 参数键: {list(params.keys())}")

        # ✅ 6. 调用服务方法（服务内部会分发到子服务）
        logger.info(f"[Modes] 🔄 [步骤6] 调用服务方法: {service_type}.{method_name}()...")
        logger.debug(f"[Modes]     - 参数数量: {len(params)}")
        logger.debug(f"[Modes]     - 关键参数:")
        logger.debug(f"[Modes]         - model: {params.get('model', 'None')}")
        logger.debug(f"[Modes]         - prompt: {params.get('prompt', 'None')[:100] + '...' if params.get('prompt') and len(params.get('prompt', '')) > 100 else params.get('prompt', 'None')}")
        if 'number_of_images' in params:
            logger.debug(f"[Modes]         - number_of_images: {params.get('number_of_images')}")
        if 'aspect_ratio' in params:
            logger.debug(f"[Modes]         - aspect_ratio: {params.get('aspect_ratio')}")
        if 'image_size' in params:
            logger.debug(f"[Modes]         - image_size: {params.get('image_size')}")
        if 'reference_images' in params:
            ref_images = params.get('reference_images', {})
            logger.debug(f"[Modes]         - reference_images: {len(ref_images)} 个引用图片")
        
        method_start = time.time()
        try:
            result = await method(**params)
        except Exception as method_error:
            # ✅ 捕获图片生成/编辑时的错误（如 API Key 过期、API 错误等）
            method_time = (time.time() - method_start) * 1000
            logger.error(f"[Modes] ❌ [步骤6] 服务方法调用失败 (耗时: {method_time:.2f}ms): {method_error}")

            if isinstance(method_error, NotImplementedError):
                raise HTTPException(
                    status_code=501,
                    detail=_build_mode_error_detail(
                        code="mode_not_implemented",
                        message=str(method_error),
                        details={
                            "provider": provider,
                            "mode": mode,
                            "service_method": method_name,
                        },
                        retryable=False,
                    ),
                )
            
            # 对于图片生成/编辑/扩图模式，需要返回友好的错误信息
            if method_name in ["generate_image", "edit_image", "expand_image"]:
                # 检查是否是 API 相关错误
                from ...services.gemini.base.imagen_common import APIError
                from ...services.gemini.base.image_edit_common import NotSupportedError

                if isinstance(method_error, NotSupportedError):
                    raise HTTPException(
                        status_code=400,
                        detail=_build_mode_error_detail(
                            code="capability_not_supported",
                            message=str(method_error),
                            details={
                                "provider": provider,
                                "mode": mode,
                                "service_method": method_name,
                                "api_type": getattr(method_error, "api_type", None),
                            },
                            retryable=False,
                        ),
                    )

                if isinstance(method_error, APIError):
                    error_message = str(method_error)
                    # 提取原始错误信息（如果是 API Key 过期等）
                    if hasattr(method_error, 'original_error'):
                        orig_error = method_error.original_error
                        if orig_error and 'API key' in str(orig_error):
                            error_message = "API Key 已过期或无效，请更新 API Key"
                    raise HTTPException(
                        status_code=400,
                        detail=_build_mode_error_detail(
                            code="image_generation_failed",
                            message=f"图片生成失败: {error_message}",
                            details={
                                "provider": provider,
                                "mode": mode,
                                "service_method": method_name,
                            },
                            retryable=False,
                        )
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=_build_mode_error_detail(
                            code="image_generation_failed",
                            message=f"图片生成失败: {str(method_error)}",
                            details={
                                "provider": provider,
                                "mode": mode,
                                "service_method": method_name,
                            },
                            retryable=False,
                        )
                    )
            elif method_name == "generate_video":
                error_message = str(method_error or "")
                status_code = _resolve_video_generation_error_status_code(method_error)
                raise HTTPException(
                    status_code=status_code,
                    detail=_build_mode_error_detail(
                        code="video_generation_failed",
                        message=f"视频生成失败: {error_message}",
                        details={
                            "provider": provider,
                            "mode": mode,
                            "service_method": method_name,
                        },
                        retryable=False,
                    ),
                )
            else:
                # 其他模式，直接抛出原始异常
                raise
        
        method_time = (time.time() - method_start) * 1000
        
        logger.info(f"[Modes] ✅ [步骤6] 服务方法调用完成 (耗时: {method_time:.2f}ms)")
        if isinstance(result, list):
            logger.debug(f"[Modes]     - 返回结果: {len(result)} 个图片")
        elif isinstance(result, dict):
            logger.debug(f"[Modes]     - 返回结果: 字典格式")
            if 'images' in result:
                logger.debug(f"[Modes]     - 图片数量: {len(result.get('images', []))}")
        else:
            logger.debug(f"[Modes]     - 返回结果类型: {type(result).__name__}")

        # ✅ 7. **新增**：处理图片生成和编辑的结果（使用 AttachmentService）
        # 对于 image-gen, image-edit, image-outpainting 模式，处理返回的图片
        if method_name in ["generate_image", "edit_image", "expand_image"]:
            logger.info(f"[Modes] 🔄 [步骤7] 处理图片生成/编辑结果...")
            attachment_service = AttachmentService(db)
            
            # 获取会话ID和消息ID
            session_id = None
            message_id = None
            if request_body.options:
                session_id = request_body.options.frontend_session_id or request_body.options.session_id
                message_id = request_body.options.message_id
            
            logger.debug(f"[Modes]     - session_id: {session_id or 'None'}")  # ✅ 不截断 ID，显示完整 ID
            logger.debug(f"[Modes]     - message_id: {message_id or 'None'}")  # ✅ 不截断 ID，显示完整 ID
            
            # ✅ 如果缺少 messageId，记录警告但继续处理（不阻塞）
            if not message_id:
                logger.warning(f"[Modes] ⚠️ 缺少 message_id，附件将不会保存到数据库")
            
            if session_id and message_id:
                processed_images = []
                
                # 处理返回的图片列表
                # 结果格式可能是 List[Dict] 或 List[ImageGenerationResult]
                images = result if isinstance(result, list) else result.get("images", []) if isinstance(result, dict) else []
                logger.debug(f"[Modes]     - 需要处理的图片数量: {len(images)}")
                
                for idx, img in enumerate(images):
                    logger.info(f"[Modes] 🔄 [步骤7] 处理第 {idx+1}/{len(images)} 张图片...")
                    
                    # 提取图片URL和MIME类型
                    # 支持多种格式：Dict 或 ImageGenerationResult
                    if isinstance(img, dict):
                        ai_url = img.get("url") or img.get("image")
                        mime_type = img.get("mime_type", "image/png")
                        filename = img.get("filename")  # ✅ 提取 filename（如果有）
                        enhanced_prompt = img.get("enhanced_prompt")  # ✅ 提取增强后的提示词
                        thoughts = img.get("thoughts")  # ✅ 修复断点1：提取思考过程
                        text = img.get("text")  # ✅ 修复断点1：提取文本响应
                    else:
                        # ImageGenerationResult 对象
                        ai_url = img.url if hasattr(img, "url") else None
                        mime_type = img.mime_type if hasattr(img, "mime_type") else "image/png"
                        filename = img.filename if hasattr(img, "filename") else None
                        enhanced_prompt = img.enhanced_prompt if hasattr(img, "enhanced_prompt") else None
                        thoughts = getattr(img, "thoughts", None)  # ✅ 修复断点1：提取思考过程
                        text = getattr(img, "text", None)  # ✅ 修复断点1：提取文本响应
                    
                    if not ai_url:
                        logger.warning(f"[Modes] ⚠️ 第 {idx+1} 张图片缺少URL，跳过")
                        continue
                    
                    url_type = "Base64" if ai_url.startswith('data:') else "HTTP" if ai_url.startswith('http') else "其他"
                    logger.debug(f"[Modes]     - 图片URL类型: {url_type}")
                    logger.debug(f"[Modes]     - mime_type: {mime_type}")
                    
                    # 使用 AttachmentService 处理AI返回的图片
                    # 根据方法名确定前缀：generated（生成）, edited（编辑）, expanded（扩图）
                    if method_name == "generate_image":
                        prefix = "generated"
                    elif method_name == "expand_image":
                        prefix = "expanded"
                    else:
                        prefix = "edited"
                    logger.debug(f"[Modes]     - 调用 AttachmentService.process_ai_result()...")
                    processed = await attachment_service.process_ai_result(
                        ai_url=ai_url,
                        mime_type=mime_type,
                        session_id=session_id,
                        message_id=message_id,
                        user_id=user_id,
                        prefix=prefix,
                        filename=filename,
                    )
                    
                    logger.info(f"[Modes] ✅ [步骤7] 第 {idx+1} 张图片处理完成:")
                    logger.debug(f"[Modes]     - attachment_id: {processed['attachment_id']}")  # ✅ 不截断 ID，显示完整 ID
                    logger.debug(f"[Modes]     - status: {processed['status']}")
                    logger.debug(f"[Modes]     - task_id: {processed.get('task_id') or 'None'}")  # ✅ 不截断 task_id，显示完整 ID
                    
                    # 构建响应格式（使用 snake_case，中间件会自动转换为 camelCase）
                    image_result = {
                        "url": processed["display_url"],  # 显示URL（前端立即显示）
                        "attachment_id": processed["attachment_id"],
                        "upload_status": processed["status"],
                        "task_id": processed["task_id"],
                        "mime_type": processed.get("mime_type") or mime_type,
                        "filename": processed.get("filename") or filename or f"{prefix}-{processed['attachment_id'][:8]}.png",
                        # ✅ 新增：返回完整的元数据，供前端保存和后续 CONTINUITY LOGIC 使用
                        "session_id": processed.get("session_id") or session_id,
                        "message_id": processed.get("message_id") or message_id,
                        "user_id": processed.get("user_id") or user_id,
                        "cloud_url": processed.get("cloud_url") or "",  # 云URL（空，待上传完成）
                    }

                    # 添加增强后的提示词（如果有）
                    if enhanced_prompt:
                        image_result["enhanced_prompt"] = enhanced_prompt
                        logger.debug(f"[Modes]     - enhanced_prompt: {enhanced_prompt}")
                    
                    # ✅ 修复断点1：保留 thinking 数据（如果存在）
                    if thoughts:
                        image_result["thoughts"] = thoughts
                        logger.debug(f"[Modes]     - thoughts: {len(thoughts) if isinstance(thoughts, list) else 'N/A'} items")
                    if text:
                        image_result["text"] = text
                        logger.debug(f"[Modes]     - text: {text[:100]}..." if len(text) > 100 else f"[Modes]     - text: {text}")
                    
                    processed_images.append(image_result)
                
                # 更新结果
                if isinstance(result, dict):
                    result["images"] = processed_images
                else:
                    result = processed_images
                
                logger.info(f"[Modes] ✅ [步骤7] 所有图片处理完成: {len(processed_images)} 张")
            else:
                logger.warning(f"[Modes] ⚠️ [步骤7] 跳过附件处理: 缺少 session_id 或 message_id")
        elif method_name == "generate_video":
            logger.info(f"[Modes] 🔄 [步骤7] 处理视频生成结果...")
            attachment_service = AttachmentService(db)

            session_id = None
            message_id = None
            if request_body.options:
                session_id = request_body.options.frontend_session_id or request_body.options.session_id
                message_id = request_body.options.message_id

            logger.debug(f"[Modes]     - session_id: {session_id or 'None'}")
            logger.debug(f"[Modes]     - message_id: {message_id or 'None'}")

            video_payload = result if isinstance(result, dict) else {}
            ai_url = video_payload.get("url")
            mime_type = video_payload.get("mime_type") or video_payload.get("mimeType") or "video/mp4"
            filename = video_payload.get("filename")
            sidecar_files = list(video_payload.get("sidecar_files") or video_payload.get("sidecarFiles") or [])
            has_provider_attachment = bool(
                video_payload.get("attachment_id") or video_payload.get("attachmentId")
            )
            provider_file_uri = str(
                video_payload.get("provider_file_uri")
                or video_payload.get("providerFileUri")
                or ""
            ).strip()
            provider_file_name = str(
                video_payload.get("provider_file_name")
                or video_payload.get("providerFileName")
                or ""
            ).strip()
            gcs_uri = str(video_payload.get("gcs_uri") or video_payload.get("gcsUri") or "").strip()
            stored_file_uri = gcs_uri or provider_file_uri or provider_file_name
            attachment_source_url = str(ai_url or stored_file_uri or "").strip()

            if has_provider_attachment:
                logger.info(f"[Modes] ✅ [步骤7] 跳过视频附件处理: Provider 已返回 attachment_id")
            elif session_id and message_id and attachment_source_url:
                processed = await attachment_service.process_ai_result(
                    ai_url=attachment_source_url,
                    mime_type=mime_type,
                    session_id=session_id,
                    message_id=message_id,
                    user_id=user_id,
                    prefix="video",
                    filename=filename,
                    file_uri=stored_file_uri or None,
                    provider_file_name=provider_file_name or None,
                    provider_file_uri=provider_file_uri or None,
                    gcs_uri=gcs_uri or None,
                )

                result = {
                    **video_payload,
                    "url": processed["display_url"],
                    "attachment_id": processed["attachment_id"],
                    "upload_status": processed["status"],
                    "task_id": processed["task_id"],
                    "mime_type": processed.get("mime_type") or mime_type,
                    "filename": processed.get("filename") or filename or f"video-{processed['attachment_id'][:8]}.mp4",
                    "session_id": processed.get("session_id") or session_id,
                    "message_id": processed.get("message_id") or message_id,
                    "user_id": processed.get("user_id") or user_id,
                    "cloud_url": processed.get("cloud_url") or "",
                }
                if processed.get("file_uri") or stored_file_uri:
                    result["file_uri"] = processed.get("file_uri") or stored_file_uri
                logger.info(f"[Modes] ✅ [步骤7] 视频结果已桥接为附件代理 URL")
            else:
                logger.warning(f"[Modes] ⚠️ [步骤7] 跳过视频附件处理: 缺少 session_id/message_id 或视频资产引用")

            if session_id and message_id and sidecar_files:
                processed_sidecars = []
                for sidecar in sidecar_files:
                    if not isinstance(sidecar, dict):
                        continue
                    sidecar_url = str(sidecar.get("data_url") or sidecar.get("url") or "").strip()
                    sidecar_mime_type = str(sidecar.get("mime_type") or sidecar.get("mimeType") or "text/vtt").strip()
                    sidecar_filename = str(sidecar.get("filename") or "").strip() or None
                    if not sidecar_url:
                        continue
                    processed_sidecar = await attachment_service.process_ai_result(
                        ai_url=sidecar_url,
                        mime_type=sidecar_mime_type,
                        session_id=session_id,
                        message_id=message_id,
                        user_id=user_id,
                        prefix="video-sidecar",
                        filename=sidecar_filename,
                    )
                    processed_sidecars.append(
                        {
                            **sidecar,
                            "url": processed_sidecar["display_url"],
                            "attachment_id": processed_sidecar["attachment_id"],
                            "upload_status": processed_sidecar["status"],
                            "task_id": processed_sidecar["task_id"],
                            "cloud_url": processed_sidecar.get("cloud_url") or "",
                            "message_id": processed_sidecar.get("message_id") or message_id,
                            "session_id": processed_sidecar.get("session_id") or session_id,
                            "user_id": processed_sidecar.get("user_id") or user_id,
                            "filename": processed_sidecar.get("filename") or sidecar_filename,
                            "mime_type": processed_sidecar.get("mime_type") or sidecar_mime_type,
                        }
                    )
                if processed_sidecars:
                    result = {
                        **(result if isinstance(result, dict) else {}),
                        "sidecar_files": processed_sidecars,
                    }

        # ✅ 8. 返回响应
        total_time = (time.time() - request_start_time) * 1000
        logger.info(f"[Modes] ========== 模式请求处理完成 (总耗时: {total_time:.2f}ms) ==========")
        logger.debug(f"[Modes]     - provider: {provider}")
        logger.debug(f"[Modes]     - mode: {mode}")
        logger.debug(f"[Modes]     - 成功: True")
        return ModeResponse(
            success=True,
            data=result,
            provider=provider,
            mode=mode
        )

    except ProviderParamValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_http_detail())
    except ValueError as e:
        logger.warning(f"[Modes] Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Modes] Error: provider={provider}, mode={mode}, error={e}", exc_info=True)
        error_text = str(e or "")
        lowered = error_text.lower()
        if (
            "resource_exhausted" in lowered
            or "exceeded your current quota" in lowered
            or "rate limit" in lowered
            or "quota" in lowered
        ):
            raise HTTPException(status_code=429, detail=error_text)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{provider}/{mode}/stream")
async def handle_mode_stream(
    provider: str,
    mode: str,
    request_body: ModeRequest,
    request: Request,
    user_id: str = Depends(require_current_user),  # ✅ 自动注入 user_id
    db: Session = Depends(get_db)
):
    """
    统一的流式模式处理端点

    支持流式响应的模式（如聊天）

    Args:
        provider: 提供商名称
        mode: 模式名称
        request_body: 请求体
        request: FastAPI 请求对象
        user_id: 用户 ID（自动注入）
        db: 数据库会话

    Returns:
        StreamingResponse: SSE 流式响应
    """
    try:
        logger.info(f"[Modes] Stream request: provider={provider}, mode={mode}, user_id={user_id}")

        option_keys = set(request_body.options.model_dump(exclude_none=True).keys()) if request_body.options else set()
        extra_keys = set(request_body.extra.keys()) if request_body.extra else set()
        validate_mode_param_keys(
            provider=provider,
            mode=mode,
            option_keys=option_keys,
            extra_keys=extra_keys,
        )

        # 1. 获取凭证
        api_key, api_url = await get_provider_credentials(
            provider=provider,
            db=db,
            user_id=user_id,
            request_api_key=request_body.api_key,
            request_base_url=request_body.options.base_url if request_body.options else None
        )

        # 2. 创建提供商服务
        service = ProviderFactory.create(
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            user_id=user_id,
            db=db
        )

        # 3. 获取服务方法
        method_name = get_service_method(mode)
        if not method_name or not is_streaming_mode(mode):
            raise ValueError(f"Mode '{mode}' does not support streaming")

        method = getattr(service, method_name)
        if not method:
            raise ValueError(f"Provider '{provider}' does not support method '{method_name}'")

        # 4. 准备参数
        params = {
            "model": request_body.model_id,
        }
        
        # 对于聊天模式，需要 messages 参数
        if mode == "chat":
            # 将 attachments 转换为 messages 格式
            if request_body.attachments:
                params["messages"] = request_body.attachments
            else:
                # 如果没有 attachments，使用 prompt 作为消息
                params["messages"] = [{"role": "user", "content": request_body.prompt}]
        else:
            params["prompt"] = request_body.prompt
        
        # 添加 options 中的参数
        if request_body.options:
            options_dict = request_body.options.model_dump(exclude_none=True)
            params.update(options_dict)
        
        # 添加 extra 参数
        if request_body.extra:
            params.update(request_body.extra)

        # ✅ 5. 流式响应
        async def generate():
            try:
                # 调用流式方法
                async for chunk in method(**params):
                    yield encode_sse_data(chunk, camel_case=True)
            except Exception as e:
                logger.error(f"[Modes] Stream error: {e}", exc_info=True)
                error_chunk = build_safe_error_chunk(
                    code="stream_error",
                    message="Mode streaming failed",
                    details={"provider": provider, "mode": mode},
                    retryable=True,
                )
                yield encode_sse_data(error_chunk, camel_case=True)
                yield encode_sse_data(_build_stream_error_done_chunk(), camel_case=True)

        return create_sse_response(generate())

    except ProviderParamValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_http_detail())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Modes] Stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
