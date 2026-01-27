"""
图像编辑 Prompt 优化器

使用 Qwen-VL-Max 模型理解输入图像，并智能优化编辑指令。

参考: Qwen-Image 官方 prompt_utils.py 中的 polish_edit_prompt 函数
"""
import io
import json
import base64
import logging
from typing import Optional, Union, Literal
from dataclasses import dataclass
import httpx

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

# DashScope 多模态 API
DASHSCOPE_VL_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


@dataclass
class EditPromptOptimizeResult:
    """编辑 Prompt 优化结果"""
    original_prompt: str
    optimized_prompt: str
    task_type: Optional[str] = None  # add/delete/replace/text/style/inpaint/outpaint
    success: bool = True
    error: Optional[str] = None


# 编辑 Prompt 优化系统提示词
EDIT_SYSTEM_PROMPT = '''# Edit Prompt Enhancer

You are a professional edit prompt enhancer. Your task is to generate a direct and specific edit prompt based on the user-provided instruction and the image input conditions.

Please strictly follow the enhancing rules below:

## 1. General Principles
- Keep the enhanced prompt **direct and specific**.
- If the instruction is contradictory, vague, or unachievable, prioritize reasonable inference and correction.
- Keep the core intention of the original instruction unchanged, only enhancing its clarity and visual feasibility.

## 2. Task-Type Handling Rules

### 1. Add, Delete, Replace Tasks
- If the instruction is clear, preserve the original intent and only refine the grammar.
- If the description is vague, supplement with minimal but sufficient details (category, color, size, position, etc.).
- For replacement tasks, specify "Replace Y with X" and briefly describe the key visual features of X.

### 2. Text Editing Tasks
- All text content must be enclosed in English double quotes `" "`. Keep the original language of the text.
- Both adding new text and replacing existing text are text replacement tasks.
- Specify text position, color, and layout only if user has required.

### 3. Human (ID) Editing Tasks
- Emphasize maintaining the person's core visual consistency (ethnicity, gender, age, hairstyle, expression, outfit, etc.).
- If modifying appearance, ensure the new element is consistent with the original style.
- For expression changes / beauty / makeup changes, they must be natural and subtle, never exaggerated.

### 4. Style Conversion Tasks
- If a style is specified, describe it concisely using key visual features.
- For colorization tasks use: "Restore and colorize the photo."

### 5. Content Filling Tasks
- For inpainting tasks: "Perform inpainting on this image. The original caption is: [description]"
- For outpainting tasks: "Extend the image beyond its boundaries using outpainting. The original caption is: [description]"

## 3. Output Format
Output ONLY a JSON object with this format:
```json
{
   "Rewritten": "your optimized edit prompt here"
}
```

Do not include any explanation or additional text outside the JSON.'''


class EditPromptOptimizer:
    """
    图像编辑 Prompt 优化器

    使用 Qwen-VL-Max 模型理解图像并优化编辑指令。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-vl-max-latest",
        timeout: float = 60.0,
        max_retries: int = 3
    ):
        """
        初始化优化器

        Args:
            api_key: DashScope API Key
            model: 视觉模型名称
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """懒加载 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def optimize(
        self,
        prompt: str,
        image: Union[str, bytes, "Image.Image"],
        enable_rewrite: bool = True
    ) -> EditPromptOptimizeResult:
        """
        优化编辑 Prompt

        Args:
            prompt: 原始编辑指令
            image: 输入图像 (URL/bytes/PIL Image)
            enable_rewrite: 是否启用 LLM 改写

        Returns:
            EditPromptOptimizeResult
        """
        prompt = prompt.strip()

        logger.info(f"[EditPromptOptimizer] 开始优化: len={len(prompt)}")

        if not enable_rewrite:
            return EditPromptOptimizeResult(
                original_prompt=prompt,
                optimized_prompt=prompt,
                success=True
            )

        try:
            # 编码图像
            image_data = self._encode_image(image)

            # 调用 VL 模型
            optimized = await self._rewrite_with_vl(prompt, image_data)

            logger.info(f"[EditPromptOptimizer] 优化成功: len={len(optimized)}")

            return EditPromptOptimizeResult(
                original_prompt=prompt,
                optimized_prompt=optimized,
                success=True
            )

        except Exception as e:
            logger.error(f"[EditPromptOptimizer] 优化失败: {str(e)}")

            return EditPromptOptimizeResult(
                original_prompt=prompt,
                optimized_prompt=prompt,  # 失败时返回原始 prompt
                success=False,
                error=str(e)
            )

    def _encode_image(self, image: Union[str, bytes, "Image.Image"]) -> str:
        """
        编码图像为 base64 data URI

        Args:
            image: 输入图像

        Returns:
            base64 data URI 或 URL
        """
        # 如果是 URL，直接返回
        if isinstance(image, str):
            if image.startswith(('http://', 'https://', 'oss://')):
                return image
            if image.startswith('data:image/'):
                return image

        # 如果是 PIL Image
        if HAS_PIL and isinstance(image, Image.Image):
            # 压缩大图像
            max_size = 2000
            if image.width > max_size or image.height > max_size:
                ratio = max_size / max(image.width, image.height)
                new_size = (int(image.width * ratio), int(image.height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"[EditPromptOptimizer] 图像已压缩至 {new_size}")

            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            return f"data:image/png;base64,{b64}"

        # 如果是 bytes
        if isinstance(image, bytes):
            b64 = base64.b64encode(image).decode('utf-8')
            return f"data:image/png;base64,{b64}"

        raise ValueError(f"不支持的图像类型: {type(image)}")

    async def _rewrite_with_vl(self, prompt: str, image_data: str) -> str:
        """
        调用视觉语言模型进行编辑 Prompt 优化

        Args:
            prompt: 原始编辑指令
            image_data: 图像数据（URL 或 base64）

        Returns:
            优化后的编辑指令
        """
        # 构建多模态消息
        user_content = [
            {"type": "image_url", "image_url": {"url": image_data}},
            {"type": "text", "text": f"User Input: {prompt}\n\nRewritten Prompt:"}
        ]

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EDIT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    DASHSCOPE_VL_URL,
                    json=payload,
                    headers=headers
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.warning(f"[EditPromptOptimizer] API 错误 (attempt {attempt + 1}): {error_text}")
                    continue

                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                if content:
                    # 解析 JSON 响应
                    optimized = self._parse_response(content)
                    return optimized

            except Exception as e:
                logger.warning(f"[EditPromptOptimizer] 请求失败 (attempt {attempt + 1}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise

        raise Exception("编辑 Prompt 优化失败，已达最大重试次数")

    def _parse_response(self, content: str) -> str:
        """
        解析 LLM 响应，提取优化后的 Prompt

        Args:
            content: LLM 响应内容

        Returns:
            优化后的 Prompt
        """
        content = content.strip()

        # 尝试解析 JSON
        try:
            # 移除可能的 markdown 代码块标记
            if '```json' in content:
                content = content.replace('```json', '').replace('```', '')
            elif '```' in content:
                content = content.replace('```', '')

            content = content.strip()
            data = json.loads(content)

            if isinstance(data, dict) and 'Rewritten' in data:
                return data['Rewritten'].strip()

        except json.JSONDecodeError:
            pass

        # 如果不是 JSON，直接返回内容
        content = content.replace("\n", " ").strip()
        return content

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
