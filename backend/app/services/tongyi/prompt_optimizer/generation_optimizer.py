"""
文生图 Prompt 优化器

使用 Qwen-Plus 模型智能改写用户输入的 Prompt，
自动分类场景（人像/含文字/通用），生成专业级图像描述。

参考: Qwen-Image 官方 prompt_utils_2512.py
"""
import logging
from typing import Optional, Literal
from dataclasses import dataclass, field
import httpx

from .language_detector import detect_language, get_magic_suffix

logger = logging.getLogger(__name__)

# DashScope API 配置
DASHSCOPE_GENERATION_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


@dataclass
class PromptOptimizerConfig:
    """Prompt 优化器配置"""
    enabled: bool = True
    model: str = "qwen-plus"
    add_magic_suffix: bool = True
    timeout: float = 30.0
    max_retries: int = 3

    # 魔法词组
    magic_suffix_zh: str = "超清，4K，电影级构图"
    magic_suffix_en: str = "Ultra HD, 4K, cinematic composition"


@dataclass
class PromptOptimizeResult:
    """Prompt 优化结果"""
    original_prompt: str
    optimized_prompt: str
    language: Literal["zh", "en"]
    scene_type: Optional[str] = None  # portrait/text/general
    magic_suffix: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


# ==================== Prompt 模板 ====================

SYSTEM_PROMPT_ZH = '''# 图像 Prompt 改写专家

你是一位世界顶级的图像 Prompt 构建专家，精通中英双语，具备卓越的视觉理解与描述能力。你的任务是将用户提供的原始图像描述，根据其内容自动归类为**人像**、**含文字图**或**通用图像**三类之一，并进行自然、精准、富有美感的中文改写。

## 基础要求
1. 使用流畅、自然的描述性语言，以连贯形式输出，禁止使用列表、编号、标题或任何结构化格式。
2. 合理丰富画面细节：
   - 判断画面是否为含文字图类型，若不是，不要添加多余的文字信息。
   - 当原始描述信息不足时，可补充符合逻辑的环境、光影、质感或氛围元素；
   - 当原始描述信息充足时，只做相应的修改；
   - 当原始描述信息过多或冗余时，在保留原意的情况下精简；
   - 所有补充内容必须与已有信息风格统一、逻辑自洽。
3. 严禁修改任何专有名词（人名、品牌名、地名、IP 名称等）。
4. 完整呈现所有文字信息：若图像包含文字，图像中显示的文字内容均使用中文双引号包含起来。
5. 明确指定整体艺术风格（如：写实摄影、动漫插画、电影海报、赛博朋克概念图、水彩手绘、3D 渲染等）。

## 子任务一：人像图像改写
当画面以人物为核心主体时：
1. 指出人物基本信息：种族、性别、大致年龄，脸型、五官特征、表情、肤色、肤质、妆容等；
2. 指出服装、发型与配饰；
3. 指出姿态与动作；
4. 指出背景与环境；
5. 内容篇幅保持简洁，输出控制在150字以内。

## 子任务二：含文字图改写
当画面包含可识别文字时：
1. 忠实还原所有文字内容，明确指出文字所在位置；
2. 描述字体风格、颜色、大小；
3. 说明文字与载体的关系（印刷、LED屏、霓虹灯、刺绣等）。

## 子任务三：通用图像改写
当画面不含人物主体或文字时：
1. 核心视觉元素：主体对象的种类、数量、形态、颜色、材质；
2. 空间层次（前景、中景、背景）；
3. 光影与色彩；
4. 场景与氛围。

请根据用户输入的内容，自动判断所属任务类型，输出一段符合上述规范的中文图像 Prompt。不要解释、不要确认、不要额外回复，仅输出改写后的 Prompt 文本。'''

SYSTEM_PROMPT_EN = '''# Image Prompt Rewriting Expert

You are a world-class expert in crafting image prompts with exceptional visual comprehension and descriptive abilities. Your task is to automatically classify the user's original image description into one of three categories—**portrait**, **text-containing image**, or **general image**—and then rewrite it naturally, precisely, and aesthetically in English.

## Core Requirements
1. Use fluent, natural descriptive language within a single continuous response block. Avoid formal Markdown lists, numbered items, or headings.
2. Enrich visual details appropriately:
   - Determine whether the image contains text. If not, do not add any extraneous textual elements.
   - When the original description lacks sufficient detail, supplement logically consistent environmental, lighting, texture, or atmospheric elements.
   - All added content must align stylistically and logically with existing information.
3. Never modify proper nouns (names, brands, locations, IP names, etc.).
4. Fully represent all textual content: If the image contains visible text, enclose every piece of displayed text in English double quotation marks (" ").
5. Clearly specify the overall artistic style (e.g., realistic photography, anime illustration, movie poster, cyberpunk concept art, watercolor painting, 3D rendering, etc.).

## Subtask 1: Portrait Image Rewriting
When the image centers on a human subject:
1. Define Subject's Identity: ethnicity, gender, specific age, facial characteristics, expression;
2. Describe clothing, hairstyle, and accessories;
3. Capture Pose and Action;
4. Depict background and environment;
5. Keep output concise, around 150 words.

## Subtask 2: Text-Containing Image Rewriting
When the image contains recognizable text:
1. Faithfully reproduce all text content, specify location;
2. Describe font style, color, size;
3. Explain the relationship between text and its carrier.

## Subtask 3: General Image Rewriting
When the image lacks human subjects or text:
1. Core visual components: subject type, quantity, form, color, material;
2. Spatial layering (foreground, midground, background);
3. Lighting and color;
4. Scene and atmosphere.

Based on the user's input, automatically determine the appropriate task category and output a single English image prompt. Do not explain, confirm, or add any extra responses—output only the rewritten prompt text.'''


class GenerationPromptOptimizer:
    """
    文生图 Prompt 优化器

    使用 Qwen-Plus 模型智能改写用户输入的 Prompt。
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[PromptOptimizerConfig] = None
    ):
        """
        初始化优化器

        Args:
            api_key: DashScope API Key
            config: 优化器配置
        """
        self.api_key = api_key
        self.config = config or PromptOptimizerConfig()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """懒加载 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client

    async def optimize(
        self,
        prompt: str,
        enable_rewrite: bool = True,
        add_magic_suffix: bool = True
    ) -> PromptOptimizeResult:
        """
        优化文生图 Prompt

        Args:
            prompt: 原始提示词
            enable_rewrite: 是否启用 LLM 改写
            add_magic_suffix: 是否添加魔法词组

        Returns:
            PromptOptimizeResult
        """
        prompt = prompt.strip()
        language = detect_language(prompt)
        magic_suffix = get_magic_suffix(language) if add_magic_suffix else ""

        logger.info(f"[PromptOptimizer] 开始优化: language={language}, len={len(prompt)}")

        # 如果禁用改写，直接返回原始 + 魔法词组
        if not enable_rewrite or not self.config.enabled:
            optimized = prompt
            if magic_suffix:
                optimized = f"{prompt}，{magic_suffix}" if language == "zh" else f"{prompt}, {magic_suffix}"

            return PromptOptimizeResult(
                original_prompt=prompt,
                optimized_prompt=optimized,
                language=language,
                magic_suffix=magic_suffix,
                success=True
            )

        # 调用 LLM 进行改写
        try:
            optimized = await self._rewrite_with_llm(prompt, language)

            # 添加魔法词组
            if magic_suffix and add_magic_suffix:
                if language == "zh":
                    optimized = f"{optimized}，{magic_suffix}"
                else:
                    optimized = f"{optimized}, {magic_suffix}"

            logger.info(f"[PromptOptimizer] 优化成功: len={len(optimized)}")

            return PromptOptimizeResult(
                original_prompt=prompt,
                optimized_prompt=optimized,
                language=language,
                magic_suffix=magic_suffix,
                success=True
            )

        except Exception as e:
            logger.error(f"[PromptOptimizer] 优化失败: {str(e)}")

            # 失败时返回原始 prompt + 魔法词组
            fallback = prompt
            if magic_suffix:
                fallback = f"{prompt}，{magic_suffix}" if language == "zh" else f"{prompt}, {magic_suffix}"

            return PromptOptimizeResult(
                original_prompt=prompt,
                optimized_prompt=fallback,
                language=language,
                magic_suffix=magic_suffix,
                success=False,
                error=str(e)
            )

    async def _rewrite_with_llm(self, prompt: str, language: str) -> str:
        """
        调用 LLM 进行 Prompt 改写

        Args:
            prompt: 原始提示词
            language: 语言代码

        Returns:
            改写后的提示词
        """
        system_prompt = SYSTEM_PROMPT_ZH if language == "zh" else SYSTEM_PROMPT_EN

        if language == "zh":
            user_content = f"用户输入：{prompt}\n改写输出："
        else:
            user_content = f"User Input: {prompt}\n\nRewritten Prompt:"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.post(
                    DASHSCOPE_GENERATION_URL,
                    json=payload,
                    headers=headers
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.warning(f"[PromptOptimizer] API 错误 (attempt {attempt + 1}): {error_text}")
                    continue

                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                if content:
                    # 清理输出
                    content = content.strip()
                    content = content.replace("\n", " ")
                    return content

            except Exception as e:
                logger.warning(f"[PromptOptimizer] 请求失败 (attempt {attempt + 1}): {str(e)}")
                if attempt == self.config.max_retries - 1:
                    raise

        raise Exception("Prompt 优化失败，已达最大重试次数")

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
