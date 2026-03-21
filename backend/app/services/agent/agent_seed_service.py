"""
Agent 种子服务 - 为用户同步默认 Agent 与示例模板依赖的种子 Agent。

建议显式传入 seeds，以区分默认初始化与示例模板补齐。
"""

import time
import logging
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from ...models.db_models import AgentRegistry, ConfigProfile, generate_uuid
from ..common.prompt_enricher import enhance_seed_agents

logger = logging.getLogger(__name__)


def _parse_saved_model_ids(raw_saved_models: Any) -> List[str]:
    raw_models = raw_saved_models or []
    if isinstance(raw_models, str):
        try:
            raw_models = json.loads(raw_models)
        except Exception:
            raw_models = []

    model_ids: List[str] = []
    if not isinstance(raw_models, list):
        return model_ids

    for item in raw_models:
        if isinstance(item, dict):
            model_id = str(item.get("id") or item.get("model_id") or "").strip()
        else:
            model_id = str(item or "").strip()
        if model_id:
            model_ids.append(model_id)
    return model_ids


def _infer_seed_task_type(seed: Dict[str, Any]) -> str:
    agent_card = seed.get("agent_card")
    if isinstance(agent_card, dict):
        defaults = agent_card.get("defaults")
        if isinstance(defaults, dict):
            task_type = str(defaults.get("defaultTaskType") or "").strip().lower().replace("_", "-")
            if task_type:
                return task_type
    return "chat"


def _looks_like_google_chat_image_edit_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if "imagen" in lowered:
        return False
    if "gemini" in lowered and "image" in lowered:
        return True
    return any(token in lowered for token in ("flash-image", "pro-image", "nano-banana"))


def _looks_like_image_edit_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if _looks_like_google_chat_image_edit_model(lowered):
        return True
    if any(token in lowered for token in ("wan2.6-image", "qwen-image-edit", "-i2i")):
        return True
    if lowered.startswith("wan") and "image" in lowered and "-t2i" not in lowered:
        return True
    if any(token in lowered for token in ("capability", "ingredients", "edit", "inpaint", "outpaint", "mask", "recontext")):
        return True
    if "imagen" in lowered and "generate" not in lowered:
        return True
    return False


def _looks_like_image_generation_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("veo", "sora", "luma", "video", "tts", "whisper", "embedding", "segmentation", "upscale", "try-on", "recontext")):
        return False
    if any(token in lowered for token in ("wan2.6-image", "qwen-image-edit", "-i2i")):
        return False
    if lowered.startswith("wan") and "image" in lowered and "-t2i" not in lowered:
        return False
    if any(token in lowered for token in ("capability", "ingredients", "edit", "inpaint", "outpaint")):
        return False
    return any(token in lowered for token in ("imagen", "image", "dall", "wanx", "-t2i", "z-image", "flux", "midjourney", "nano-banana"))


def _looks_like_vision_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("veo", "sora", "luma", "video", "tts", "audio", "speech", "whisper", "embedding", "segmentation", "upscale")):
        return False
    if any(token in lowered for token in ("imagen", "wanx", "dall", "midjourney", "flux", "-t2i", "z-image", "wan2.6-image", "qwen-image-edit")):
        return False
    if _looks_like_google_chat_image_edit_model(lowered):
        return True
    if "gemini" in lowered and any(token in lowered for token in ("flash", "pro", "image")):
        return True
    if "-vl-" in lowered or lowered.endswith("-vl"):
        return True
    return any(token in lowered for token in ("gpt-4o", "claude-3", "qwen-vl", "qwen2-vl", "qwen2.5-vl"))


def _looks_like_text_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    blocked_tokens = (
        "imagen", "image", "wanx", "dall", "midjourney", "-t2i",
        "veo", "sora", "luma", "video", "tts", "whisper", "embedding", "segmentation", "upscale",
        "try-on", "tryon", "recontext", "inpaint", "outpaint",
        "edit", "mask", "aqa", "-vl-", "audio", "speech", "realtime", "live",
    )
    return not any(token in lowered for token in blocked_tokens)


def _looks_like_video_generation_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("veo", "sora", "luma")):
        return True
    return "video" in lowered and not any(token in lowered for token in ("vision", "audio", "speech", "whisper"))


def _looks_like_audio_generation_model(model_id: str) -> bool:
    lowered = str(model_id or "").lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("whisper", "asr", "transcribe", "transcription")):
        return False
    return (
        lowered.startswith("tts")
        or "-tts" in lowered
        or "speech" in lowered
    )


def _is_model_compatible_for_task(model_id: str, task_type: str) -> bool:
    normalized_task = str(task_type or "chat").strip().lower().replace("_", "-")
    if normalized_task in {"image-gen"}:
        return _looks_like_image_generation_model(model_id)
    if normalized_task in {"image-edit"}:
        return _looks_like_image_edit_model(model_id)
    if normalized_task in {"video-gen"}:
        return _looks_like_video_generation_model(model_id)
    if normalized_task in {"audio-gen"}:
        return _looks_like_audio_generation_model(model_id)
    if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
        return _looks_like_vision_model(model_id)
    return _looks_like_text_model(model_id) or _looks_like_vision_model(model_id)


def _rank_model_for_task(model_id: str, task_type: str) -> Tuple[int, float]:
    lowered = str(model_id or "").lower()
    normalized_task = str(task_type or "chat").strip().lower().replace("_", "-")

    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", lowered)]
    version_score = max(numbers) if numbers else 0.0
    preview_penalty = 1 if any(flag in lowered for flag in ("preview", "-exp", "_exp", "experimental")) else 0

    if normalized_task == "image-gen":
        if "imagen" in lowered and "generate" in lowered:
            family_rank = 0
        elif any(token in lowered for token in ("-t2i", "wanx")):
            family_rank = 1
        elif "dall" in lowered:
            family_rank = 2
        elif "image" in lowered:
            family_rank = 3
        else:
            family_rank = 9
        return (family_rank + preview_penalty, -version_score)

    if normalized_task == "image-edit":
        if any(token in lowered for token in ("wan2.6-image", "qwen-image-edit", "-i2i")):
            family_rank = 0
        elif _looks_like_google_chat_image_edit_model(lowered):
            family_rank = 1
        elif _looks_like_image_edit_model(lowered):
            family_rank = 2
        else:
            family_rank = 9
        return (family_rank + preview_penalty, -version_score)

    if normalized_task == "video-gen":
        if lowered.startswith("veo-3.1"):
            family_rank = 0
        elif lowered.startswith("veo-3.0"):
            family_rank = 1
        elif "veo" in lowered:
            family_rank = 2
        elif "sora" in lowered:
            family_rank = 3
        elif _looks_like_video_generation_model(lowered):
            family_rank = 4
        else:
            family_rank = 9
        return (family_rank + preview_penalty, -version_score)

    if normalized_task == "audio-gen":
        if lowered.startswith("tts-1-hd"):
            family_rank = 0
        elif lowered.startswith("tts-1"):
            family_rank = 1
        elif "gpt-4o-mini-tts" in lowered:
            family_rank = 2
        elif "speech" in lowered:
            family_rank = 3
        elif _looks_like_audio_generation_model(lowered):
            family_rank = 4
        else:
            family_rank = 9
        return (family_rank + preview_penalty, -version_score)

    if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
        if "-vl-" in lowered or "qwen-vl" in lowered or "qwen2.5-vl" in lowered:
            family_rank = 0
        elif _looks_like_google_chat_image_edit_model(lowered):
            family_rank = 1
        elif _looks_like_vision_model(lowered):
            family_rank = 2
        else:
            family_rank = 9
        return (family_rank + preview_penalty, -version_score)

    if "gemini" in lowered and "2.5-pro" in lowered:
        family_rank = 0
    elif "gemini" in lowered and "2.5-flash" in lowered:
        family_rank = 1
    elif "qwen-plus" in lowered:
        family_rank = 2
    elif "qwen" in lowered:
        family_rank = 3
    else:
        family_rank = 4
    return (family_rank + preview_penalty, -version_score)


def _default_model_for_provider_task(provider_id: str, task_type: str) -> str:
    lowered = str(provider_id or "").strip().lower()
    normalized_task = str(task_type or "chat").strip().lower().replace("_", "-")
    if lowered.startswith("google"):
        if normalized_task == "image-gen":
            return "imagen-3.0-generate-002"
        if normalized_task == "image-edit":
            return "gemini-2.5-flash-image"
        if normalized_task == "video-gen":
            return "veo-3.1-generate-preview"
        if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
            return "gemini-2.5-flash-image"
        return "gemini-2.5-flash"
    if lowered.startswith("tongyi") or lowered.startswith("dashscope"):
        if normalized_task == "image-gen":
            return "wan2.6-t2i"
        if normalized_task == "image-edit":
            return "wan2.6-image"
        if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
            return "qwen2.5-vl-7b-instruct"
        return "qwen-plus"
    if lowered.startswith("openai"):
        if normalized_task == "image-gen":
            return "dall-e-3"
        if normalized_task == "audio-gen":
            return "tts-1"
        if normalized_task in {"vision-understand", "image-understand", "vision-analyze", "image-analyze"}:
            return "gpt-4o"
        return "gpt-4o-mini"
    if lowered.startswith("ollama"):
        return "llama3.1:8b"
    return ""


def _load_user_profiles_for_seed(db: Session, user_id: str) -> List[ConfigProfile]:
    try:
        profiles = db.query(ConfigProfile).filter(ConfigProfile.user_id == user_id).all()
        return [profile for profile in profiles if getattr(profile, "api_key", None)]
    except Exception:
        logger.debug("[AgentSeed] ConfigProfile table unavailable when loading seed profiles", exc_info=True)
        return []


def _resolve_seed_provider_and_model(seed: Dict[str, Any], profiles: List[ConfigProfile]) -> Tuple[str, str]:
    seed_provider = str(seed.get("provider_id") or "").strip()
    seed_model = str(seed.get("model_id") or "").strip()
    task_type = _infer_seed_task_type(seed)

    if not profiles:
        return seed_provider, seed_model

    provider_models: Dict[str, List[str]] = {}
    provider_display: Dict[str, str] = {}
    profile_order = sorted(
        profiles,
        key=lambda profile: -int(getattr(profile, "updated_at", 0) or 0),
    )
    ordered_provider_ids: List[str] = []
    for profile in profile_order:
        provider_id = str(getattr(profile, "provider_id", "") or "").strip()
        if not provider_id:
            continue
        provider_key = provider_id.lower()
        if provider_key not in provider_models:
            provider_models[provider_key] = []
            provider_display[provider_key] = provider_id
            ordered_provider_ids.append(provider_key)
        for model_id in _parse_saved_model_ids(getattr(profile, "saved_models", None)):
            if model_id not in provider_models[provider_key]:
                provider_models[provider_key].append(model_id)

    if not ordered_provider_ids:
        return seed_provider, seed_model

    seed_provider_key = seed_provider.lower()
    selected_provider_key = ""
    if seed_provider_key in provider_models:
        selected_provider_key = seed_provider_key
    elif len(ordered_provider_ids) == 1:
        selected_provider_key = ordered_provider_ids[0]
    else:
        for provider_key in ordered_provider_ids:
            candidate_models = provider_models.get(provider_key, [])
            if any(_is_model_compatible_for_task(model_id, task_type) for model_id in candidate_models):
                selected_provider_key = provider_key
                break
        if not selected_provider_key:
            selected_provider_key = ordered_provider_ids[0]

    selected_provider_id = provider_display.get(selected_provider_key, seed_provider)
    model_candidates = [
        model_id for model_id in provider_models.get(selected_provider_key, [])
        if _is_model_compatible_for_task(model_id, task_type)
    ]
    model_candidates.sort(key=lambda model_id: _rank_model_for_task(model_id, task_type))

    if model_candidates:
        return selected_provider_id, model_candidates[0]

    if selected_provider_key == seed_provider_key and _is_model_compatible_for_task(seed_model, task_type):
        return selected_provider_id, seed_model

    fallback_model = _default_model_for_provider_task(selected_provider_id, task_type)
    if fallback_model:
        return selected_provider_id, fallback_model
    return seed_provider or selected_provider_id, seed_model


SEED_AGENTS: List[Dict[str, Any]] = [
    {
        "name": "亚马逊广告分析师",
        "description": "专业分析 Amazon SP/SB/SD 广告数据，提供 ACOS/ROAS 优化建议",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "📊",
        "color": "#3b82f6",
        "temperature": 0.3,
        "max_tokens": 4096,
        "system_prompt": """你是一位资深的亚马逊广告分析师，专精于 Amazon PPC 广告数据分析。

## 核心能力
- 分析 SP（Sponsored Products）、SB（Sponsored Brands）、SD（Sponsored Display）三种广告类型的投放数据
- 计算和解读关键指标：ACOS、ROAS、CTR、CVR、CPC、Impressions、Spend、Sales
- 识别高效词和无效词，优化广告投放结构
- 提供竞价策略和预算分配建议

## 分析框架
1. **数据概览**: 整体广告表现总结（花费、销售额、ACOS）
2. **Campaign 分析**: 各广告活动表现对比，识别高/低效 Campaign
3. **关键词分析**: 高转化词、高花费低转化词、长尾机会词
4. **优化建议**: 竞价调整、否定关键词、预算重新分配、新词建议

## 输出规范
- 使用 Markdown 表格展示数据对比
- 关键数字使用粗体标注
- 每个建议都要有数据支撑
- 使用中文回答""",
    },
    {
        "name": "亚马逊选品分析师",
        "description": "评估市场容量、竞争度、利润率，辅助选品决策",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "🔍",
        "color": "#8b5cf6",
        "temperature": 0.4,
        "max_tokens": 4096,
        "system_prompt": """你是一位经验丰富的亚马逊选品分析师，帮助卖家做出明智的选品决策。

## 核心能力
- 市场容量评估：分析类目月搜索量、销售量、增长趋势
- 竞争度分析：评估 Review 数量分布、品牌集中度、新品机会
- 利润率计算：考虑采购成本、FBA 费用、广告成本、退货率
- 季节性判断：识别产品的季节波动和趋势周期

## 分析维度
1. **市场规模**: 月均搜索量、销售额、增长率
2. **竞争格局**: Top 10 卖家份额、Review 门槛、新品存活率
3. **利润空间**: 售价区间、FBA 费用、预估净利润率
4. **风险评估**: 季节性、合规风险、供应链风险、侵权风险
5. **综合评分**: 1-10 分综合评级和建议

## 输出规范
- 使用数据支撑每个结论
- 明确给出"建议/观望/不建议"的选品结论
- 使用中文回答""",
    },
    {
        "name": "Listing优化专家",
        "description": "优化标题、五点、描述、A+内容，提升转化率",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "✍️",
        "color": "#10b981",
        "temperature": 0.6,
        "max_tokens": 4096,
        "system_prompt": """你是一位专业的亚马逊 Listing 优化专家，精通 A9/A10 搜索算法和消费者心理。

## 核心能力
- 标题优化：关键词布局、品牌词+核心词+属性词+场景词结构
- 五点描述（Bullet Points）：卖点提炼、痛点解决方案、使用场景
- 产品描述：故事化叙述、SEO 优化、移动端可读性
- A+ 内容规划：模块布局、图文配合、品牌故事

## 优化原则
1. 关键词自然融入，不堆砌
2. 突出差异化卖点和 USP（独特销售主张）
3. 解决买家痛点，而非罗列参数
4. 符合 Amazon 风格指南和字符限制
5. 移动端优先（80% 用户通过手机浏览）

## 输出格式
- 标题：200 字符以内，提供 2-3 个方案
- 五点：每点以大写关键词开头，150 字符以内
- 描述：2000 字符以内，HTML 格式
- A+ 建议：模块类型 + 文案 + 图片方向

## 使用中文回答""",
    },
    {
        "name": "关键词研究专家",
        "description": "搜索词挖掘、长尾关键词研究、关键词分组策略",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "🔑",
        "color": "#f59e0b",
        "temperature": 0.3,
        "max_tokens": 4096,
        "system_prompt": """你是一位亚马逊关键词研究专家，精通搜索词挖掘和关键词策略。

## 核心能力
- 核心词挖掘：从产品特征、使用场景、目标人群维度发散关键词
- 长尾词拓展：根据搜索意图分类（信息型/导航型/交易型）
- 关键词分组：按主题、匹配类型、投放阶段组织关键词
- 竞品词分析：分析竞品标题和广告中使用的关键词

## 分析框架
1. **种子词提取**: 从产品信息中识别核心种子词
2. **词根拓展**: 同义词、相关词、修饰词组合
3. **长尾延伸**: 场景词、人群词、功能词、材质词
4. **分组归类**: 按搜索量/竞争度/相关度分为 Tier 1/2/3
5. **否定词建议**: 识别不相关的搜索词

## 输出规范
- 关键词按优先级分组，使用表格展示
- 标注预估搜索量级别（高/中/低）
- 提供广告匹配类型建议（精准/词组/广泛）
- 使用中文回答""",
    },
    {
        "name": "竞品分析专家",
        "description": "分析竞品 Listing、定价策略、广告打法、评论特征",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "🎯",
        "color": "#ef4444",
        "temperature": 0.4,
        "max_tokens": 4096,
        "system_prompt": """你是一位亚马逊竞品分析专家，善于从公开数据中提取竞争情报。

## 核心能力
- Listing 对比分析：标题结构、卖点差异、图片策略
- 定价策略分析：价格带分布、促销节奏、优惠券策略
- 评论分析：好评卖点、差评痛点、Review 增长趋势
- 广告策略推断：通过搜索结果分析竞品的广告投放策略

## 分析维度
1. **基础信息**: BSR 排名、Review 数/评分、上架时间、价格
2. **Listing 质量**: 标题SEO、图片质量、A+内容、视频
3. **定价策略**: 历史价格走势、促销频率、会员价
4. **Review 洞察**: 好评关键词云、差评痛点排序、评论真实度
5. **机会缺口**: 竞品未满足的需求、可差异化的方向

## 输出规范
- 使用对比表格直观展示差异
- 明确标注可借鉴和可超越的点
- 给出具体的差异化建议
- 使用中文回答""",
    },
    {
        "name": "数据报表分析师",
        "description": "通用表格数据分析，发现趋势和异常，生成洞察报告",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "📈",
        "color": "#06b6d4",
        "temperature": 0.3,
        "max_tokens": 4096,
        "system_prompt": """你是一位专业的数据分析师，擅长从表格数据中提取有价值的商业洞察。

## 核心能力
- 数据清洗与理解：自动识别数据字段含义和数据类型
- 趋势分析：识别时间序列趋势、同比/环比变化
- 异常检测：发现数据中的异常值和异常模式
- 可视化建议：推荐最合适的图表类型展示数据

## 分析流程
1. **数据理解**: 识别字段、数据类型、数据量、时间范围
2. **描述性统计**: 均值、中位数、标准差、分位数
3. **趋势发现**: 增长率、周期性、季节性、拐点
4. **异常标记**: 离群值、缺失值、不一致数据
5. **洞察提炼**: 3-5 条关键发现 + 行动建议

## 输出规范
- 使用 Markdown 表格展示关键统计
- 趋势用箭头标注（↑ ↓ →）
- 每个洞察附带置信度（高/中/低）
- 使用中文回答""",
    },
    {
        "name": "电商文案创作师",
        "description": "创作产品文案、营销邮件、社交媒体内容",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "✏️",
        "color": "#ec4899",
        "temperature": 0.8,
        "max_tokens": 4096,
        "system_prompt": """你是一位创意出色的电商文案创作师，精通多平台内容营销。

## 核心能力
- 产品文案：标题、卖点文案、详情页文案、包装文案
- 营销内容：促销邮件、品牌故事、节日营销文案
- 社交媒体：Instagram/Facebook/TikTok 帖子文案
- 多语言：支持中英双语创作

## 创作原则
1. AIDA 模型：注意力 → 兴趣 → 欲望 → 行动
2. 以用户痛点为切入点
3. 具体数字胜过形容词
4. 简洁有力，避免冗长
5. 适配不同平台的调性和长度要求

## 输出格式
- 提供 2-3 个不同风格的方案
- 标注适用场景和平台
- 附带 CTA（行动号召）建议
- 默认中文创作，可按需提供英文版本""",
    },
    {
        "name": "产品图片设计师",
        "description": "产品主图、场景图、信息图的创意设计和提示词生成",
        "provider_id": "google",
        "model_id": "imagen-3.0-generate-002",
        "icon": "🎨",
        "color": "#a855f7",
        "temperature": 0.7,
        "max_tokens": 4096,
        "system_prompt": """你是一位专业的电商产品图片设计师，擅长创意构图和 AI 图片生成提示词编写。

## 核心能力
- 主图设计：白底产品图构图、角度选择、光影建议
- 场景图设计：生活场景、使用场景、氛围营造
- 信息图设计：卖点图文排版、尺寸标注、对比图
- AI 提示词：为 DALL-E、Midjourney、Imagen 编写精准提示词

## 设计原则
1. 亚马逊主图规范：白底 (RGB 255,255,255)、产品占比 85%+
2. 移动端优先：关键信息在缩略图中可见
3. A+ 内容规范：970x600 / 970x300 模块尺寸
4. 品牌一致性：色调、字体、风格统一

## 输出格式
- 详细的图片设计方案描述
- AI 图片生成提示词（中英双语）
- 构图参考和视觉风格建议
- 使用中文回答""",
        "agent_card": {
            "defaults": {
                "defaultTaskType": "image-gen",
                "preferLatestModel": True,
                "imageGeneration": {
                    "aspectRatio": "1:1",
                    "resolutionTier": "1K",
                    "numberOfImages": 1,
                    "outputMimeType": "image/png",
                    "promptExtend": True,
                    "addMagicSuffix": True,
                },
            }
        },
    },
    {
        "name": "图片编辑优化师",
        "description": "图片背景替换、合规检查、优化建议",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash-image",
        "icon": "🖼️",
        "color": "#f97316",
        "temperature": 0.5,
        "max_tokens": 4096,
        "system_prompt": """你是一位图片编辑和优化专家，精通电商平台图片规范和视觉优化。

## 核心能力
- 图片编辑指导：背景替换、裁剪建议、色调调整
- 合规检查：Amazon/Shopify/eBay 图片规范审查
- 优化建议：构图改进、光影调整、色彩增强
- 批量处理：多图一致性检查和优化方案

## 检查清单
1. **技术规范**: 尺寸 ≥ 1000x1000px、JPEG/PNG、文件大小 < 10MB
2. **主图合规**: 纯白背景、无文字/水印/logo、无道具
3. **内容质量**: 清晰度、色彩准确度、无变形
4. **视觉效果**: 专业感、一致性、吸引力

## 输出格式
- 合规问题清单和修复建议
- 具体的编辑操作步骤
- 优化前后对比说明
- 使用中文回答""",
        "agent_card": {
            "defaults": {
                "defaultTaskType": "image-edit",
                "preferLatestModel": True,
                "imageEdit": {
                    "editMode": "image-chat-edit",
                    "imageSize": "1K",
                    "resolutionTier": "1K",
                    "numberOfImages": 1,
                    "outputMimeType": "image/png",
                    "promptExtend": True,
                    "addMagicSuffix": True,
                    "preserveProductIdentity": True,
                    "productMatchThreshold": 72,
                    "maxRetries": 2,
                    "outputLanguage": "en",
                },
            }
        },
    },
    {
        "name": "图片视觉理解师",
        "description": "基于附件图片做主体识别、材质颜色提取、可编辑约束输出",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash-image",
        "icon": "🧠",
        "color": "#6366f1",
        "temperature": 0.2,
        "max_tokens": 4096,
        "system_prompt": """你是一位电商视觉理解专家，专门负责图片理解与结构化提炼。

## 核心原则
1. 只根据附件图片像素做判断，不根据文件名/URL/历史上下文猜测
2. 结论必须可被视觉证据支持，不确定信息标记为 unknown
3. 输出应能直接服务后续图生图和卖点图设计

## 输出要求
- 主体识别（品类/结构/关键部件）
- 颜色与材质识别（按可见证据）
- 可保留元素（后续编辑必须保留）
- 需规避元素（后续编辑禁止引入）
- 编辑约束（构图/文案安全区/主体完整性）

默认使用中文说明，字段和关键词可按下游需求输出英文。""",
        "agent_card": {
            "defaults": {
                "defaultTaskType": "vision-understand",
                "preferLatestModel": True,
                "visionUnderstand": {
                    "outputFormat": "json",
                },
            }
        },
    },
    {
        "name": "视频创意导演",
        "description": "文生视频分镜策划、镜头语言设计与视频生成提示词编排",
        "provider_id": "google",
        "model_id": "veo-3.1-generate-preview",
        "icon": "🎬",
        "color": "#6366f1",
        "temperature": 0.65,
        "max_tokens": 4096,
        "system_prompt": """你是一位专业的视频创意导演，负责把用户的创意目标转化为可执行的视频生成方案。

## 核心能力
- 拆解镜头语言：景别、运动、节奏、光线、氛围
- 设计视频结构：开场、主体动作、转场、结尾
- 约束画面一致性：主体、风格、色彩、运镜稳定性
- 输出适合视频生成模型的高质量提示词

## 输出要求
1. 先明确主体、场景、动作、镜头、风格
2. 对不明确的部分做最小必要假设，不擅自扩写剧情
3. 默认输出适合 5-8 秒短视频的提示词
4. 使用中文回答，必要时补充英文关键词""",
        "agent_card": {
            "defaults": {
                "defaultTaskType": "video-gen",
                "preferLatestModel": True,
                "videoGeneration": {
                    "aspectRatio": "16:9",
                    "resolution": "2K",
                    "durationSeconds": 5,
                },
            }
        },
    },
    {
        "name": "语音旁白制作师",
        "description": "将脚本整理为可直接生成的旁白文本，并输出自然语音参数建议",
        "provider_id": "openai",
        "model_id": "tts-1",
        "icon": "🎧",
        "color": "#06b6d4",
        "temperature": 0.45,
        "max_tokens": 4096,
        "system_prompt": """你是一位专业的语音旁白制作师，专门负责脚本整理、旁白节奏控制与语音生成提示。

## 核心能力
- 压缩与润色旁白脚本，保证朗读自然
- 根据用途选择语速、停顿、情绪和音色
- 对长文本做分段，避免旁白节奏失衡
- 输出适合 TTS 模型的最终稿

## 输出要求
1. 保持信息完整，但优先保证口语化和可听性
2. 默认输出适合中文旁白的自然表达
3. 必要时给出语速、语气和重音建议
4. 使用中文回答""",
        "agent_card": {
            "defaults": {
                "defaultTaskType": "audio-gen",
                "preferLatestModel": True,
                "audioGeneration": {
                    "voice": "alloy",
                    "responseFormat": "mp3",
                    "speed": 1,
                },
            }
        },
    },
    {
        "name": "亚马逊合规审核师",
        "description": "审核标题/五点/描述是否符合 Amazon 政策与站点风格",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "🛡️",
        "color": "#0ea5e9",
        "temperature": 0.2,
        "max_tokens": 4096,
        "system_prompt": """你是一位资深的亚马逊合规审核专家，负责审核 Listing 文案是否可上线。

## 核心能力
- 检查标题、五点、描述是否违反 Amazon 政策（夸大承诺、医疗暗示、绝对化词汇等）
- 按站点语言和类目习惯优化可读性与信息完整度
- 保留高转化信息的同时降低审核风险

## 审核输出要求
1. 合规结论：Pass / Pass with edits / Fail
2. 风险点清单：逐条列出原文问题 + 风险级别（P0/P1/P2）
3. 修订建议：提供可直接替换的合规文案
4. 最终可上线版本：标题 + 五点 + 描述

默认使用中文说明，文案可按用户目标站点输出对应语言。""",
    },
    {
        "name": "多店铺运营整合师",
        "description": "整合多卖家/多店铺商品信息，提炼统一卖点并输出可执行策略",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "🧭",
        "color": "#22c55e",
        "temperature": 0.35,
        "max_tokens": 4096,
        "system_prompt": """你是一位多店铺亚马逊运营整合专家，擅长从多来源数据中提炼统一策略。

## 核心能力
- 识别多卖家商品信息中的共性卖点与差异化机会
- 按类目/价格带/人群进行分层，形成可复用运营模板
- 输出可落地的 Listing、广告、素材协同策略

## 输出要求
1. 数据结构化映射（字段识别、缺失值、异常值）
2. 多店铺对比结论（共性、差异、优先级）
3. 可执行动作（标题策略、五点策略、关键词策略）
4. 风险与验证计划（上线前检查 + 7天复盘指标）

默认使用中文回答。""",
    },
    {
        "name": "客户沟通专家",
        "description": "买家消息回复、差评处理、售后服务模板",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "💬",
        "color": "#14b8a6",
        "temperature": 0.5,
        "max_tokens": 4096,
        "system_prompt": """你是一位专业的亚马逊客户沟通专家，精通买家沟通和客户服务。

## 核心能力
- 买家消息回复：解答产品问题、物流查询、退换货处理
- 差评应对：分析差评原因、撰写专业回复、请求修改策略
- 售后服务：退款处理话术、产品替换沟通、VoC（客户之声）分析
- 合规沟通：遵守 Amazon 沟通政策，避免违规操作

## 沟通原则
1. **24小时内响应**: 及时性是关键
2. **同理心先行**: 先理解客户感受，再解决问题
3. **解决方案导向**: 不辩解，直接提供解决方案
4. **合规第一**: 不诱导好评、不提供站外补偿
5. **专业友好**: 保持专业但温暖的语气

## 输出格式
- 提供中英双语回复模板
- 标注场景适用性
- 附带跟进策略建议
- 默认提供英文回复（面向海外买家）""",
    },
    {
        "name": "运营策略顾问",
        "description": "整体运营策略规划、节日营销方案、库存管理建议",
        "provider_id": "google",
        "model_id": "gemini-2.5-flash",
        "icon": "🧠",
        "color": "#6366f1",
        "temperature": 0.5,
        "max_tokens": 4096,
        "system_prompt": """你是一位资深的亚马逊运营策略顾问，拥有全盘运营视角和丰富的实战经验。

## 核心能力
- 运营策略规划：新品推广计划、成熟期维护策略、清货方案
- 节日营销：Prime Day、黑五网一、圣诞季等大促策划
- 库存管理：补货时机、安全库存、FBA 仓储优化
- 多站点布局：北美/欧洲/日本站点差异化运营

## 策略框架
1. **现状诊断**: 分析当前运营数据和竞争位置
2. **目标设定**: SMART 原则制定阶段性目标
3. **策略制定**: 产品/定价/广告/内容四维策略
4. **执行计划**: 时间节点、资源分配、KPI 设定
5. **复盘优化**: 数据回顾、策略调整、经验沉淀

## 输出规范
- 使用时间线/甘特图形式展示计划
- 每个建议附带优先级（P0/P1/P2）和预期效果
- 风险提示和应急预案
- 使用中文回答""",
    },
]

SEED_AGENTS = enhance_seed_agents(SEED_AGENTS)


def get_default_seed_agents() -> List[Dict[str, Any]]:
    return list(SEED_AGENTS)


def get_media_seed_agents() -> List[Dict[str, Any]]:
    return [
        seed for seed in SEED_AGENTS
        if _infer_seed_task_type(seed) in {"video-gen", "audio-gen"}
    ]


def ensure_seed_agents(db: Session, user_id: str, seeds: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    确保用户拥有种子 Agent，若无则自动创建。

    Returns: 新创建的 Agent 数量
    """
    existing_agents = db.query(AgentRegistry).filter(
        AgentRegistry.user_id == user_id,
    ).all()
    active_agents_by_name = {}
    for agent in existing_agents:
        normalized_name = str(agent.name or "").strip().lower()
        if not normalized_name:
            continue
        if str(agent.status or "").strip().lower() != "active":
            continue
        active_agents_by_name[normalized_name] = agent

    configured_profiles = _load_user_profiles_for_seed(db=db, user_id=user_id)
    now = int(time.time() * 1000)
    created = 0
    updated = 0

    for seed in (list(seeds) if seeds is not None else SEED_AGENTS):
        normalized_name = str(seed.get("name") or "").strip().lower()
        seed_default_provider = str(seed.get("provider_id") or "").strip()
        seed_task_type = _infer_seed_task_type(seed)
        target_provider, target_model = _resolve_seed_provider_and_model(
            seed=seed,
            profiles=configured_profiles,
        )
        if not target_provider:
            target_provider = seed_default_provider
        if not target_model:
            target_model = str(seed.get("model_id") or "").strip()

        active_agent = active_agents_by_name.get(normalized_name)
        if active_agent:
            if str(active_agent.agent_type or "").strip().lower() == "seed":
                changed = False
                current_provider = str(active_agent.provider_id or "").strip()
                current_model = str(active_agent.model_id or "").strip()

                should_align_provider = (
                    not current_provider
                    or current_provider == seed_default_provider
                )
                if target_provider and should_align_provider and current_provider != target_provider:
                    active_agent.provider_id = target_provider
                    changed = True

                if target_model and (
                    not current_model
                    or current_model.lower().startswith("gemini-2.0-")
                    or (
                        str(active_agent.provider_id or "").strip() == target_provider
                        and not _is_model_compatible_for_task(current_model, seed_task_type)
                    )
                    or (
                        str(active_agent.provider_id or "").strip() == target_provider
                        and current_provider != target_provider
                    )
                ):
                    active_agent.model_id = target_model
                    changed = True
                if not str(active_agent.description or "").strip() and str(seed.get("description") or "").strip():
                    active_agent.description = str(seed.get("description") or "").strip()
                    changed = True
                if isinstance(seed.get("agent_card"), dict) and not str(active_agent.agent_card_json or "").strip():
                    active_agent.agent_card_json = json.dumps(seed.get("agent_card"), ensure_ascii=False)
                    changed = True
                if changed:
                    active_agent.updated_at = now
                    updated += 1
            continue

        agent = AgentRegistry(
            id=generate_uuid(),
            user_id=user_id,
            name=seed["name"],
            description=seed["description"],
            agent_type="seed",
            provider_id=target_provider,
            model_id=target_model,
            system_prompt=seed["system_prompt"],
            temperature=seed["temperature"],
            max_tokens=seed["max_tokens"],
            icon=seed["icon"],
            color=seed["color"],
            status="active",
            created_at=now,
            updated_at=now,
            agent_card_json=(
                json.dumps(seed.get("agent_card"), ensure_ascii=False)
                if isinstance(seed.get("agent_card"), dict)
                else None
            ),
        )
        db.add(agent)
        created += 1
        active_agents_by_name[normalized_name] = agent

    if created > 0 or updated > 0:
        db.commit()
        logger.info(
            f"[AgentSeed] Synced seed agents for user {user_id}: created={created}, updated={updated}"
        )

    return created
