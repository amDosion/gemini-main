"""
视频 Prompt 优化器。

使用通义兼容模式的文本模型改写视频生成/编辑提示词，输出可直接传给视频模型的单段描述。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from .generation_optimizer import DASHSCOPE_GENERATION_URL
from .language_detector import detect_language

logger = logging.getLogger(__name__)


@dataclass
class VideoPromptOptimizeResult:
    original_prompt: str
    optimized_prompt: str
    language: Literal["zh", "en"]
    success: bool = True
    error: Optional[str] = None


SYSTEM_PROMPT_ZH = """# 视频 Prompt 改写专家

你是一位专业的视频生成与视频编辑 Prompt 专家。请将用户的原始描述改写成一段可直接用于视频模型的中文提示词。

要求：
1. 保留用户原意、主体身份、动作、风格、限制条件和负向要求，不要改变专有名词。
2. 补足视频需要的动态信息，包括主体动作、镜头运动、构图、景别、光线、节奏、时间变化和场景连续性。
3. 如果是模糊描述，只补充合理且必要的细节；如果描述已经明确，只做清晰化和专业化表达。
4. 不要输出标题、列表、Markdown、解释或确认，只输出改写后的单段 Prompt。"""

SYSTEM_PROMPT_EN = """# Video Prompt Rewriting Expert

You are a professional video generation and video editing prompt expert. Rewrite the user's input into one concise prompt that can be sent directly to a video model.

Requirements:
1. Preserve the user's intent, subject identity, actions, style, constraints, and negative requirements. Do not alter proper nouns.
2. Add video-specific details when useful, including motion, camera movement, framing, shot scale, lighting, pacing, time changes, and scene continuity.
3. If the original prompt is vague, add only reasonable necessary details. If it is already specific, refine it for clarity and visual actionability.
4. Output only the rewritten prompt as a single paragraph. Do not include headings, lists, Markdown, explanations, or confirmation."""


class VideoPromptOptimizer:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "qwen-plus",
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def optimize(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
    ) -> VideoPromptOptimizeResult:
        original_prompt = str(prompt or "").strip()
        language = detect_language(original_prompt)
        if not original_prompt:
            return VideoPromptOptimizeResult(
                original_prompt="",
                optimized_prompt="",
                language=language,
                success=False,
                error="empty prompt",
            )

        try:
            optimized = await self._rewrite_with_llm(original_prompt, language, model=model)
            return VideoPromptOptimizeResult(
                original_prompt=original_prompt,
                optimized_prompt=optimized,
                language=language,
                success=True,
            )
        except Exception as exc:
            logger.warning("[VideoPromptOptimizer] 优化失败，使用原始 Prompt: %s", exc)
            return VideoPromptOptimizeResult(
                original_prompt=original_prompt,
                optimized_prompt=original_prompt,
                language=language,
                success=False,
                error=str(exc),
            )

    async def _rewrite_with_llm(
        self,
        prompt: str,
        language: str,
        *,
        model: Optional[str] = None,
    ) -> str:
        selected_model = str(model or self.model).strip() or self.model
        system_prompt = SYSTEM_PROMPT_ZH if language == "zh" else SYSTEM_PROMPT_EN
        user_content = (
            f"用户输入：{prompt}\n改写输出："
            if language == "zh"
            else f"User input: {prompt}\n\nRewritten prompt:"
        )
        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.7,
            "max_tokens": 1200,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = ""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    DASHSCOPE_GENERATION_URL,
                    json=payload,
                    headers=headers,
                )
                if response.status_code != 200:
                    last_error = response.text
                    logger.warning(
                        "[VideoPromptOptimizer] API 错误 (attempt %s): %s",
                        attempt + 1,
                        last_error,
                    )
                    continue

                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip().replace("\n", " ")
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "[VideoPromptOptimizer] 请求失败 (attempt %s): %s",
                    attempt + 1,
                    last_error,
                )

        raise RuntimeError(last_error or "Video prompt optimization failed")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
