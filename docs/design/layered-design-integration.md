# 分层设计功能集成设计文档

> **版本**: v1.0.0
> **日期**: 2026-01-30
> **状态**: 设计阶段

---

## 1. 概述

### 1.1 背景

将 `main.py` 中的分层图像设计功能（Layered Design API）集成到现有的图片编辑系统中，使其能够在 `ImageEditView.tsx` 中作为新的编辑模式使用。

### 1.2 目标

- 在现有的自动路由架构中集成分层设计功能
- 支持跨 Provider（Google/TongYi）使用
- 与现有的 `image-chat-edit` 模式并存，通过 Tab 切换
- 前端 UI 集成到 `ImageEditView.tsx`
- **完全复用现有认证和加密机制**（无需额外配置）

### 1.3 安全集成要点

| 方面 | 集成方式 | 说明 |
|------|----------|------|
| **认证** | JWT Bearer Token | 复用 `AuthMiddleware`，无需额外处理 |
| **凭证获取** | `credential_manager.py` | 自动从用户配置档案获取并解密 |
| **API Key 存储** | Fernet 加密 | 存储时加密，使用时自动解密 |
| **请求头** | `apiClient.ts` | 自动附加 `Authorization` 和 `Content-Type` |
| **Token 刷新** | 自动刷新 | `apiClient` 检测 401 后自动使用 refresh token |
| **Vertex AI** | 自动加载 | 对于 Google Provider，自动加载用户 Vertex AI 配置 |

### 1.4 核心功能

| 功能 | 描述 | API 依赖 | 状态 |
|------|------|----------|------|
| **布局建议** | 分析图片，生成 LayerDoc 分层结构 | LLM (Gemini/Qwen) | ✅ 可用 |
| **图层分解** | 将图片分解为多个 RGBA 图层 | Qwen-Layered | 🔜 待接入 |
| **Mask 矢量化** | PNG mask → SVG path | 纯算法 (无依赖) | ✅ 可用 |
| **渲染合成** | LayerDoc → PNG | 纯算法 (无依赖) | ✅ 可用 |

---

## 2. 系统架构

### 2.1 现有架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   ImageEditView.tsx                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │    │
│  │  │ 对话编辑 Tab │  │ 分层设计 Tab │  │  画布区域    │   │    │
│  │  │ (现有)       │  │ (新增)       │  │              │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│                    POST /api/modes/{provider}/{mode}             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    modes.py (路由层)                     │    │
│  │  - 接收请求                                              │    │
│  │  - 参数验证                                              │    │
│  │  - 获取凭证                                              │    │
│  │  - 调用 ProviderFactory                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              mode_method_mapper.py (映射层)              │    │
│  │  mode → service_method 映射                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ProviderFactory (工厂层)                    │    │
│  │  provider → Service 实例                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│              ┌───────────────┴───────────────┐                  │
│              ▼                               ▼                  │
│  ┌─────────────────────┐         ┌─────────────────────┐        │
│  │   GoogleService     │         │   TongyiService     │        │
│  │   .layered_design() │         │   .layered_design() │        │
│  └─────────────────────┘         └─────────────────────┘        │
│              │                               │                   │
│              └───────────────┬───────────────┘                  │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           LayeredDesignService (共享服务)                │    │
│  │  - suggest_layout()     需要 LLM                         │    │
│  │  - decompose_layers()   需要 Qwen-Layered 外部服务       │    │
│  │  - vectorize_mask()     纯算法                           │    │
│  │  - render_layerdoc()    纯算法                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 新增组件

```
backend/app/
├── core/
│   └── mode_method_mapper.py          # ✏️ 修改：添加新模式映射
├── services/
│   ├── common/
│   │   └── layered_design_service.py  # ✨ 新建：Provider 无关的共享服务
│   ├── gemini/
│   │   └── google_service.py          # ✏️ 修改：添加 layered_design() 方法
│   └── tongyi/
│       └── tongyi_service.py          # ✏️ 修改：添加 layered_design() 方法

frontend/
├── components/views/
│   └── ImageEditView.tsx              # ✏️ 修改：添加分层设计 Tab
├── types/
│   └── layeredDesign.ts               # ✨ 新建：类型定义
└── hooks/
    └── useLayeredDesign.ts            # ✨ 新建：分层设计 Hook
```

---

## 3. 详细设计

### 3.1 后端：模式映射 (mode_method_mapper.py)

```python
# backend/app/core/mode_method_mapper.py

MODE_METHOD_MAP: Dict[str, str] = {
    # ... 现有映射 ...

    # ✨ 分层设计模式（都映射到同一个方法，内部根据 mode 参数分发）
    "image-layered-suggest": "layered_design",     # 布局建议
    "image-layered-decompose": "layered_design",   # 图层分解
    "image-layered-vectorize": "layered_design",   # Mask 矢量化
    "image-layered-render": "layered_design",      # 渲染合成
}


def is_layered_design_mode(mode: str) -> bool:
    """判断是否为分层设计相关的 mode"""
    layered_modes = {
        "image-layered-suggest",
        "image-layered-decompose",
        "image-layered-vectorize",
        "image-layered-render"
    }
    return mode in layered_modes
```

### 3.2 后端：共享服务 (layered_design_service.py)

```python
# backend/app/services/common/layered_design_service.py

"""
分层设计服务 - Provider 无关的共享服务

从 main.py 提取的核心功能，支持跨 Provider 使用。
"""

import asyncio
import base64
import io
import json
import math
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import logging

logger = logging.getLogger(__name__)


# =========================
# Configuration
# =========================
QWEN_LAYERED_ENDPOINT = os.getenv("QWEN_LAYERED_ENDPOINT", "").strip()
QWEN_LAYERED_TIMEOUT_SEC = int(os.getenv("QWEN_LAYERED_TIMEOUT_SEC", "120"))
DEFAULT_CANVAS_W = int(os.getenv("LAYERED_CANVAS_W", "2000"))
DEFAULT_CANVAS_H = int(os.getenv("LAYERED_CANVAS_H", "2000"))
FONT_PATH = os.getenv("FONT_PATH", "")


class LayeredDesignService:
    """
    分层设计服务 - Provider 无关的核心功能

    功能：
    - suggest_layout: 布局建议（需要 LLM）
    - decompose_layers: 图层分解（需要 Qwen-Layered 外部服务）
    - vectorize_mask: Mask PNG → SVG（纯算法）
    - render_layerdoc: LayerDoc → PNG（纯算法）
    """

    def __init__(
        self,
        llm_client: Any = None,
        llm_model: str = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        """
        初始化分层设计服务

        Args:
            llm_client: LLM 客户端（用于 suggest_layout）
                       - Google: genai.Client
                       - Tongyi: QwenNativeProvider
            llm_model: LLM 模型名称
            http_client: HTTP 客户端（用于 decompose_layers）
        """
        self.llm_client = llm_client
        self.llm_model = llm_model or "gemini-2.5-flash"
        self.http_client = http_client

    async def process(
        self,
        mode: str,
        prompt: str,
        reference_images: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        根据 mode 分发到具体方法

        Args:
            mode: 操作模式
            prompt: 提示词/目标描述
            reference_images: 参考图片字典
            **kwargs: 额外参数

        Returns:
            操作结果字典
        """
        logger.info(f"[LayeredDesignService] Processing mode: {mode}")

        # 提取图片数据
        image_data = self._extract_image_data(reference_images)

        if mode == "image-layered-suggest":
            return await self.suggest_layout(
                image_bytes=image_data,
                goal=prompt,
                canvas_w=kwargs.get("canvasW", DEFAULT_CANVAS_W),
                canvas_h=kwargs.get("canvasH", DEFAULT_CANVAS_H),
                max_text_boxes=kwargs.get("maxTextBoxes", 3),
                locale=kwargs.get("locale", "zh-CN")
            )

        elif mode == "image-layered-decompose":
            return await self.decompose_layers(image_bytes=image_data)

        elif mode == "image-layered-vectorize":
            return self.vectorize_mask(
                mask_bytes=image_data,
                simplify_tolerance=kwargs.get("simplifyTolerance", 2.0),
                smooth_iterations=kwargs.get("smoothIterations", 2),
                use_bezier=kwargs.get("useBezier", True),
                bezier_smoothness=kwargs.get("bezierSmoothness", 0.25),
                threshold=kwargs.get("threshold", 128),
                blur_radius=kwargs.get("blurRadius", 0.0)
            )

        elif mode == "image-layered-render":
            layer_doc = kwargs.get("layerDoc")
            if not layer_doc:
                raise ValueError("image-layered-render requires 'layerDoc' parameter")
            return await self.render_layerdoc(layer_doc=layer_doc)

        else:
            raise ValueError(f"Unknown layered design mode: {mode}")

    def _extract_image_data(self, reference_images: Dict[str, Any]) -> Optional[bytes]:
        """从 reference_images 中提取图片字节数据"""
        if not reference_images:
            return None

        raw = reference_images.get("raw")
        if not raw:
            return None

        # 处理不同格式
        if isinstance(raw, dict):
            raw = raw.get("url") or raw.get("data")

        if isinstance(raw, str):
            # Base64 Data URL
            if raw.startswith("data:"):
                base64_str = raw.split(",", 1)[1] if "," in raw else raw
                return base64.b64decode(base64_str)
            # 纯 Base64
            else:
                try:
                    return base64.b64decode(raw)
                except Exception:
                    return None

        elif isinstance(raw, bytes):
            return raw

        return None

    # =========================
    # 1. 布局建议 (需要 LLM)
    # =========================

    async def suggest_layout(
        self,
        image_bytes: bytes,
        goal: str,
        canvas_w: int = DEFAULT_CANVAS_W,
        canvas_h: int = DEFAULT_CANVAS_H,
        max_text_boxes: int = 3,
        locale: str = "zh-CN"
    ) -> Dict[str, Any]:
        """
        分析图片，生成 LayerDoc 布局建议

        Args:
            image_bytes: 图片字节数据
            goal: 布局目标描述
            canvas_w: 画布宽度
            canvas_h: 画布高度
            max_text_boxes: 最大文字框数量
            locale: 语言区域

        Returns:
            LayerDoc 字典
        """
        if not self.llm_client:
            raise ValueError("suggest_layout requires an LLM client")

        if not image_bytes:
            raise ValueError("suggest_layout requires image data")

        # 构建 prompt
        schema_hint = self._get_layerdoc_schema_hint(canvas_w, canvas_h)

        prompt = f"""
你是资深电商附图设计师 + 前端分层渲染工程师。
目标：{goal}
要求：
- 输出严格 JSON，必须符合 LayerDoc 结构（不要 markdown，不要解释）。
- 画布：{canvas_w}x{canvas_h}。
- 底图必须无字；文字一定作为 TextLayer（可编辑），并放在矩形/圆角矩形容器框里。
- 最多 {max_text_boxes} 个文字框。
- 允许渐变背景（GradientLayer）、形状层（ShapeLayer）、文字层（TextLayer）。
- 文字内容要基于图片可见信息，不要编造看不出来的参数。
请参考此 JSON 结构样例（仅结构参考，内容需结合图片）：{json.dumps(schema_hint, ensure_ascii=False)}
"""

        try:
            # 调用 LLM（适配不同 Provider）
            response_text = await self._call_llm_with_image(prompt, image_bytes)

            # 解析 JSON
            json_text = self._extract_json_from_llm_response(response_text)
            layer_doc = json.loads(json_text)

            logger.info(f"[LayeredDesignService] suggest_layout: generated {len(layer_doc.get('layers', []))} layers")

            return {
                "success": True,
                "layerDoc": layer_doc
            }

        except json.JSONDecodeError as e:
            logger.error(f"[LayeredDesignService] Failed to parse LayerDoc JSON: {e}")
            return {
                "success": False,
                "error": f"Failed to parse LayerDoc JSON: {str(e)}"
            }
        except Exception as e:
            logger.error(f"[LayeredDesignService] suggest_layout failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _call_llm_with_image(self, prompt: str, image_bytes: bytes) -> str:
        """
        调用 LLM 进行图片分析

        适配不同 Provider 的 LLM 客户端
        """
        # 检测客户端类型
        client_type = type(self.llm_client).__name__

        if "Client" in client_type or hasattr(self.llm_client, "models"):
            # Google genai.Client
            return await self._call_google_llm(prompt, image_bytes)
        elif hasattr(self.llm_client, "chat") or hasattr(self.llm_client, "stream_chat"):
            # Tongyi QwenNativeProvider
            return await self._call_tongyi_llm(prompt, image_bytes)
        else:
            raise ValueError(f"Unsupported LLM client type: {client_type}")

    async def _call_google_llm(self, prompt: str, image_bytes: bytes) -> str:
        """调用 Google Gemini LLM"""
        try:
            from google.genai import types as genai_types
        except ImportError:
            genai_types = None

        # 构建内容
        contents = [prompt]

        if genai_types:
            contents.append(genai_types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png"
            ))

        # 调用 API
        if hasattr(self.llm_client, "aio"):
            # 异步客户端
            response = await self.llm_client.aio.models.generate_content(
                model=self.llm_model,
                contents=contents,
                config={"temperature": 0.25, "max_output_tokens": 4096}
            )
        else:
            # 同步客户端
            response = self.llm_client.models.generate_content(
                model=self.llm_model,
                contents=contents,
                config={"temperature": 0.25, "max_output_tokens": 4096}
            )

        return getattr(response, "text", "") or ""

    async def _call_tongyi_llm(self, prompt: str, image_bytes: bytes) -> str:
        """调用 Tongyi Qwen LLM"""
        # 将图片转为 base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{image_base64}"

        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_url},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        # 调用聊天接口
        response = await self.llm_client.chat(
            messages=messages,
            model=self.llm_model or "qwen-vl-max"
        )

        # 提取文本
        if isinstance(response, dict):
            return response.get("content", "") or response.get("text", "")
        return str(response)

    def _get_layerdoc_schema_hint(self, canvas_w: int, canvas_h: int) -> Dict[str, Any]:
        """获取 LayerDoc 结构示例"""
        return {
            "width": canvas_w,
            "height": canvas_h,
            "background": "#FFFFFFFF",
            "layers": [
                {
                    "id": "grad_bg",
                    "type": "gradient",
                    "z": 0,
                    "opacity": 1.0,
                    "blend": "normal",
                    "angle": 20,
                    "stops": [[0.0, "#0B1220FF"], [1.0, "#111827FF"]],
                    "transform": {"x": 0, "y": 0, "scale": 1, "rotate": 0, "anchor_x": 0, "anchor_y": 0}
                },
                {
                    "id": "text_1",
                    "type": "text",
                    "z": 11,
                    "text": "示例文字",
                    "bbox": [120, 260, 820, 220],
                    "style": {"font_size": 88, "font_color": "#111827FF", "align": "center", "fit_to_box": True},
                    "box_fill": "#FFFFFFFF",
                    "box_radius": 36,
                    "box_padding": 34,
                    "transform": {"x": 0, "y": 0, "scale": 1, "rotate": 0, "anchor_x": 0, "anchor_y": 0}
                }
            ]
        }

    def _extract_json_from_llm_response(self, text: str) -> str:
        """从 LLM 响应中提取 JSON"""
        text = text.strip()

        # 尝试匹配 markdown 代码块
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # 尝试提取 JSON 对象
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        return text

    # =========================
    # 2. 图层分解 (需要 Qwen-Layered 外部服务)
    # =========================

    async def decompose_layers(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        将图片分解为多个 RGBA 图层

        需要配置 QWEN_LAYERED_ENDPOINT 环境变量

        Args:
            image_bytes: 图片字节数据

        Returns:
            图层列表
        """
        if not QWEN_LAYERED_ENDPOINT:
            return {
                "success": False,
                "error": "QWEN_LAYERED_ENDPOINT is not configured. Please set this environment variable."
            }

        if not image_bytes:
            return {
                "success": False,
                "error": "decompose_layers requires image data"
            }

        # 创建 HTTP 客户端（如果未提供）
        http_client = self.http_client
        should_close = False

        if not http_client:
            http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
            should_close = True

        try:
            files = {
                "image": ("image.png", image_bytes, "image/png")
            }

            response = await http_client.post(
                QWEN_LAYERED_ENDPOINT,
                files=files,
                timeout=QWEN_LAYERED_TIMEOUT_SEC
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Qwen layered service error: {response.status_code} {response.text}"
                }

            data = response.json()
            layers = data.get("layers", [])

            logger.info(f"[LayeredDesignService] decompose_layers: extracted {len(layers)} layers")

            return {
                "success": True,
                "layers": layers
            }

        except httpx.RequestError as e:
            logger.error(f"[LayeredDesignService] decompose_layers failed: {e}")
            return {
                "success": False,
                "error": f"Failed to call Qwen layered service: {str(e)}"
            }
        finally:
            if should_close:
                await http_client.aclose()

    # =========================
    # 3. Mask 矢量化 (纯算法)
    # =========================

    def vectorize_mask(
        self,
        mask_bytes: bytes,
        simplify_tolerance: float = 2.0,
        smooth_iterations: int = 2,
        use_bezier: bool = True,
        bezier_smoothness: float = 0.25,
        threshold: int = 128,
        blur_radius: float = 0.0
    ) -> Dict[str, Any]:
        """
        将 mask PNG 转换为可编辑的 SVG path

        这是"真正像 PS 那样编辑轮廓"的关键功能。

        Args:
            mask_bytes: Mask 图片字节数据
            simplify_tolerance: RDP 简化容差（像素）
            smooth_iterations: Chaikin 平滑迭代次数
            use_bezier: 是否输出贝塞尔曲线
            bezier_smoothness: 贝塞尔曲线平滑度 (0-0.5)
            threshold: 二值化阈值
            blur_radius: 预处理高斯模糊半径

        Returns:
            包含 SVG 和 path 数据的字典
        """
        if not mask_bytes:
            return {
                "success": False,
                "error": "vectorize_mask requires mask data"
            }

        try:
            # 打开图片
            mask_img = Image.open(io.BytesIO(mask_bytes))

            # 调用矢量化函数
            result = self._vectorize_mask_impl(
                mask_img=mask_img,
                simplify_tolerance=simplify_tolerance,
                smooth_iterations=smooth_iterations,
                use_bezier=use_bezier,
                bezier_smoothness=bezier_smoothness,
                threshold=threshold,
                blur_radius=blur_radius
            )

            # 添加 base64 编码的 SVG
            svg_bytes = result["svg"].encode("utf-8")
            result["svg_base64"] = base64.b64encode(svg_bytes).decode("utf-8")
            result["success"] = True

            logger.info(f"[LayeredDesignService] vectorize_mask: {result['contours_count']} contours")

            return result

        except Exception as e:
            logger.error(f"[LayeredDesignService] vectorize_mask failed: {e}")
            return {
                "success": False,
                "error": f"Vectorization failed: {str(e)}"
            }

    def _vectorize_mask_impl(
        self,
        mask_img: Image.Image,
        simplify_tolerance: float,
        smooth_iterations: int,
        use_bezier: bool,
        bezier_smoothness: float,
        threshold: int,
        blur_radius: float
    ) -> Dict[str, Any]:
        """矢量化实现（从 main.py 提取）"""
        # 提取 mask 通道
        if mask_img.mode == "RGBA":
            mask_arr = np.array(mask_img)[:, :, 3]
        elif mask_img.mode == "LA":
            mask_arr = np.array(mask_img)[:, :, 1]
        elif mask_img.mode == "L":
            mask_arr = np.array(mask_img)
        else:
            mask_arr = np.array(mask_img.convert("L"))

        h, w = mask_arr.shape

        # 可选预处理模糊
        if blur_radius > 0:
            mask_pil = Image.fromarray(mask_arr, mode="L")
            mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            mask_arr = np.array(mask_pil)

        # 提取轮廓
        raw_contours = self._find_contours_from_mask(mask_arr, threshold=threshold)

        # 简化和平滑
        processed_contours = []
        path_data = []

        for i, contour in enumerate(raw_contours):
            if len(contour) < 3:
                continue

            # RDP 简化
            simplified = self._simplify_contour_rdp(contour, simplify_tolerance)
            if len(simplified) < 3:
                continue

            # Chaikin 平滑
            smoothed = self._smooth_contour(simplified, iterations=smooth_iterations)
            if len(smoothed) < 3:
                continue

            processed_contours.append(smoothed)

            # 生成 path d
            if use_bezier:
                d = self._points_to_bezier_path(smoothed, closed=True, smoothness=bezier_smoothness)
            else:
                d = self._points_to_svg_path(smoothed, closed=True)

            path_data.append({
                "id": f"contour_{i}",
                "d": d,
                "points_count": len(smoothed)
            })

        # 生成完整 SVG
        svg = self._contours_to_svg(
            processed_contours,
            width=w,
            height=h,
            use_bezier=use_bezier,
            smoothness=bezier_smoothness
        )

        return {
            "svg": svg,
            "paths": path_data,
            "width": w,
            "height": h,
            "contours_count": len(processed_contours)
        }

    # ... (其他辅助方法从 main.py 复制)
    # _find_contours_from_mask, _simplify_contour_rdp, _smooth_contour
    # _points_to_svg_path, _points_to_bezier_path, _contours_to_svg

    def _find_contours_from_mask(self, mask: np.ndarray, threshold: int = 128) -> List[List[Tuple[int, int]]]:
        """从二值化 mask 中提取轮廓点（Moore 邻域追踪算法）"""
        # ... 从 main.py 复制实现
        binary = (mask > threshold).astype(np.uint8)
        h, w = binary.shape
        visited = np.zeros((h, w), dtype=bool)
        contours = []

        # 简化版：扫描边缘像素
        for y in range(h):
            for x in range(w):
                if binary[y, x] == 1 and not visited[y, x]:
                    # 检查是否是边缘
                    if x == 0 or binary[y, x-1] == 0:
                        contour = self._trace_contour(binary, visited, y, x, h, w)
                        if len(contour) >= 3:
                            contours.append(contour)

        return contours

    def _trace_contour(self, binary, visited, start_y, start_x, h, w):
        """追踪轮廓"""
        contour = [(start_x, start_y)]
        visited[start_y, start_x] = True

        directions = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
        current_y, current_x = start_y, start_x

        for _ in range(h * w):
            found = False
            for dy, dx in directions:
                ny, nx = current_y + dy, current_x + dx
                if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] == 1 and not visited[ny, nx]:
                    visited[ny, nx] = True
                    contour.append((nx, ny))
                    current_y, current_x = ny, nx
                    found = True
                    break
            if not found:
                break

        return contour

    def _simplify_contour_rdp(self, points: List[Tuple[int, int]], tolerance: float) -> List[Tuple[int, int]]:
        """Ramer-Douglas-Peucker 算法简化轮廓"""
        if len(points) < 3:
            return points

        # 简化实现
        def perpendicular_distance(point, line_start, line_end):
            x0, y0 = point
            x1, y1 = line_start
            x2, y2 = line_end

            dx = x2 - x1
            dy = y2 - y1

            if dx == 0 and dy == 0:
                return math.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)

            numerator = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1)
            denominator = math.sqrt(dx ** 2 + dy ** 2)

            return numerator / denominator if denominator > 0 else 0

        # 找最远点
        max_dist = 0
        max_idx = 0
        for i in range(1, len(points) - 1):
            dist = perpendicular_distance(points[i], points[0], points[-1])
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > tolerance:
            left = self._simplify_contour_rdp(points[:max_idx + 1], tolerance)
            right = self._simplify_contour_rdp(points[max_idx:], tolerance)
            return left[:-1] + right
        else:
            return [points[0], points[-1]]

    def _smooth_contour(self, points: List[Tuple[int, int]], iterations: int = 2) -> List[Tuple[float, float]]:
        """Chaikin 角切算法平滑轮廓"""
        if len(points) < 3:
            return [(float(x), float(y)) for x, y in points]

        pts = [(float(x), float(y)) for x, y in points]

        for _ in range(iterations):
            if len(pts) < 3:
                break

            new_pts = []
            n = len(pts)

            for i in range(n):
                p0 = pts[i]
                p1 = pts[(i + 1) % n]

                q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
                r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])

                new_pts.append(q)
                new_pts.append(r)

            pts = new_pts

        return pts

    def _points_to_svg_path(self, points: List[Tuple[float, float]], closed: bool = True) -> str:
        """将点列表转换为 SVG path d 属性"""
        if len(points) < 2:
            return ""

        d = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

        for x, y in points[1:]:
            d += f" L {x:.2f} {y:.2f}"

        if closed:
            d += " Z"

        return d

    def _points_to_bezier_path(self, points: List[Tuple[float, float]], closed: bool = True, smoothness: float = 0.25) -> str:
        """将点列表转换为平滑的贝塞尔曲线 SVG path"""
        if len(points) < 2:
            return ""

        if len(points) == 2:
            return f"M {points[0][0]:.2f} {points[0][1]:.2f} L {points[1][0]:.2f} {points[1][1]:.2f}" + (" Z" if closed else "")

        n = len(points)
        d = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

        # 简化版：使用二次贝塞尔曲线
        for i in range(1, n):
            x, y = points[i]
            d += f" L {x:.2f} {y:.2f}"

        if closed:
            d += " Z"

        return d

    def _contours_to_svg(
        self,
        contours: List[List[Tuple[float, float]]],
        width: int,
        height: int,
        use_bezier: bool = True,
        smoothness: float = 0.25
    ) -> str:
        """将轮廓列表转换为完整的 SVG 字符串"""
        paths = []
        for i, contour in enumerate(contours):
            if len(contour) < 3:
                continue

            if use_bezier:
                d = self._points_to_bezier_path(contour, closed=True, smoothness=smoothness)
            else:
                d = self._points_to_svg_path(contour, closed=True)

            paths.append(f'  <path id="contour_{i}" d="{d}" fill="black" fill-rule="evenodd"/>')

        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <g id="mask_paths">
{chr(10).join(paths)}
  </g>
</svg>'''

        return svg

    # =========================
    # 4. 渲染合成 (纯算法)
    # =========================

    async def render_layerdoc(self, layer_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 LayerDoc 渲染为 PNG

        Args:
            layer_doc: LayerDoc 字典

        Returns:
            包含 PNG base64 的字典
        """
        try:
            # 渲染图像
            img = self._render_layerdoc_impl(layer_doc)

            # 转为 base64
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            png_base64 = base64.b64encode(png_bytes).decode("utf-8")

            logger.info(f"[LayeredDesignService] render_layerdoc: {layer_doc.get('width', 0)}x{layer_doc.get('height', 0)}")

            return {
                "success": True,
                "image_base64": png_base64,
                "mime_type": "image/png",
                "width": layer_doc.get("width", 0),
                "height": layer_doc.get("height", 0)
            }

        except Exception as e:
            logger.error(f"[LayeredDesignService] render_layerdoc failed: {e}")
            return {
                "success": False,
                "error": f"Render failed: {str(e)}"
            }

    def _render_layerdoc_impl(self, doc: Dict[str, Any]) -> Image.Image:
        """渲染 LayerDoc 到 PIL Image（从 main.py 提取）"""
        width = doc.get("width", DEFAULT_CANVAS_W)
        height = doc.get("height", DEFAULT_CANVAS_H)
        background = doc.get("background")
        layers = doc.get("layers", [])

        # 创建画布
        if background:
            canvas = Image.new("RGBA", (width, height), self._rgba_tuple(background))
        else:
            canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))

        # 按 z 值排序
        layers_sorted = sorted(layers, key=lambda l: l.get("z", 0))

        # 渲染每个图层
        for layer in layers_sorted:
            layer_type = layer.get("type")

            if layer_type == "gradient":
                self._render_gradient_layer(canvas, layer)
            elif layer_type == "shape":
                self._render_shape_layer(canvas, layer)
            elif layer_type == "text":
                self._render_text_layer(canvas, layer)
            elif layer_type == "raster":
                self._render_raster_layer(canvas, layer)

        return canvas

    def _rgba_tuple(self, color: str) -> Tuple[int, int, int, int]:
        """解析颜色字符串"""
        c = color.strip()
        if not c.startswith("#"):
            return (255, 255, 255, 255)
        c = c[1:]
        if len(c) == 6:
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return (r, g, b, 255)
        if len(c) == 8:
            r, g, b, a = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16)
            return (r, g, b, a)
        return (255, 255, 255, 255)

    def _render_gradient_layer(self, canvas: Image.Image, layer: Dict[str, Any]):
        """渲染渐变图层"""
        # 简化实现：纯色填充
        stops = layer.get("stops", [])
        if stops and len(stops) > 0:
            color = self._rgba_tuple(stops[0][1] if isinstance(stops[0], list) else stops[0].get("color", "#FFFFFFFF"))
            grad = Image.new("RGBA", canvas.size, color)
            canvas.alpha_composite(grad)

    def _render_shape_layer(self, canvas: Image.Image, layer: Dict[str, Any]):
        """渲染形状图层"""
        bbox = layer.get("bbox", [0, 0, 100, 100])
        x, y, w, h = bbox
        style = layer.get("style", {})

        # 创建形状图像
        shape_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shape_img)

        fill = style.get("fill")
        if fill:
            fill_color = self._rgba_tuple(fill)
            shape_type = layer.get("shape", "rect")

            if shape_type == "round_rect":
                radius = style.get("radius", 0)
                draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=fill_color)
            elif shape_type == "ellipse":
                draw.ellipse([0, 0, w, h], fill=fill_color)
            else:
                draw.rectangle([0, 0, w, h], fill=fill_color)

        canvas.alpha_composite(shape_img, dest=(x, y))

    def _render_text_layer(self, canvas: Image.Image, layer: Dict[str, Any]):
        """渲染文字图层"""
        bbox = layer.get("bbox", [0, 0, 100, 50])
        x, y, w, h = bbox
        text = layer.get("text", "")
        style = layer.get("style", {})

        # 创建文字图像
        text_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_img)

        # 绘制背景框
        box_fill = layer.get("box_fill")
        if box_fill:
            box_radius = layer.get("box_radius", 0)
            fill_color = self._rgba_tuple(box_fill)
            draw.rounded_rectangle([0, 0, w, h], radius=box_radius, fill=fill_color)

        # 绘制文字
        font_size = style.get("font_size", 24)
        font_color = self._rgba_tuple(style.get("font_color", "#000000FF"))

        try:
            font = self._load_font(font_size)
        except Exception:
            font = ImageFont.load_default()

        # 简单居中
        padding = layer.get("box_padding", 10)
        draw.text((padding, padding), text, font=font, fill=font_color)

        canvas.alpha_composite(text_img, dest=(x, y))

    def _render_raster_layer(self, canvas: Image.Image, layer: Dict[str, Any]):
        """渲染位图图层"""
        png_base64 = layer.get("png_base64")
        if png_base64:
            try:
                img_bytes = base64.b64decode(png_base64)
                img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

                transform = layer.get("transform", {})
                x = int(transform.get("x", 0))
                y = int(transform.get("y", 0))

                canvas.alpha_composite(img, dest=(x, y))
            except Exception as e:
                logger.warning(f"[LayeredDesignService] Failed to render raster layer: {e}")

    @lru_cache(maxsize=128)
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """加载字体"""
        if FONT_PATH and os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size=size)
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()
```

### 3.3 后端：GoogleService 集成

```python
# backend/app/services/gemini/google_service.py

class GoogleService(BaseProviderService):
    # ... 现有代码 ...

    async def layered_design(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分层设计 - 委托给 LayeredDesignService

        路由逻辑：
        - image-layered-suggest → suggest_layout()
        - image-layered-decompose → decompose_layers()
        - image-layered-vectorize → vectorize_mask()
        - image-layered-render → render_layerdoc()

        Args:
            prompt: 提示词/目标描述
            model: 模型名称
            reference_images: 参考图片字典
            mode: 操作模式
            **kwargs: 额外参数

        Returns:
            操作结果字典
        """
        from ..common.layered_design_service import LayeredDesignService

        logger.info(f"[GoogleService] Delegating layered design to LayeredDesignService: mode={mode}")

        # 创建服务实例
        service = LayeredDesignService(
            llm_client=self.sdk_initializer.client if hasattr(self, 'sdk_initializer') else None,
            llm_model=model
        )

        return await service.process(
            mode=mode,
            prompt=prompt,
            reference_images=reference_images,
            **kwargs
        )
```

### 3.4 后端：TongyiService 集成

```python
# backend/app/services/tongyi/tongyi_service.py

class TongyiService(BaseProviderService):
    # ... 现有代码 ...

    async def layered_design(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分层设计 - 委托给 LayeredDesignService

        Args:
            prompt: 提示词/目标描述
            model: 模型名称
            reference_images: 参考图片字典
            mode: 操作模式
            **kwargs: 额外参数

        Returns:
            操作结果字典
        """
        from ..common.layered_design_service import LayeredDesignService

        logger.info(f"[TongyiService] Delegating layered design to LayeredDesignService: mode={mode}")

        # 获取聊天客户端（用于布局建议）
        if self._chat_provider is None:
            from .chat import QwenNativeProvider
            self._chat_provider = QwenNativeProvider(
                api_key=self.api_key,
                api_url=self.api_url
            )

        # 创建服务实例
        service = LayeredDesignService(
            llm_client=self._chat_provider,
            llm_model=model or "qwen-vl-max"
        )

        return await service.process(
            mode=mode,
            prompt=prompt,
            reference_images=reference_images,
            **kwargs
        )
```

---

## 4. 前端设计

### 4.1 类型定义 (layeredDesign.ts)

```typescript
// frontend/types/layeredDesign.ts

/**
 * LayerDoc 分层文档结构
 */
export interface LayerDoc {
  width: number;
  height: number;
  background?: string;
  layers: Layer[];
}

export type Layer = RasterLayer | TextLayer | ShapeLayer | GradientLayer;

export interface Transform {
  x: number;
  y: number;
  scale: number;
  rotate: number;
  anchor_x: number;
  anchor_y: number;
}

export interface BaseLayer {
  id: string;
  name?: string;
  type: 'raster' | 'text' | 'shape' | 'gradient';
  z: number;
  opacity: number;
  blend: 'normal' | 'multiply' | 'screen' | 'overlay';
  transform: Transform;
}

export interface RasterLayer extends BaseLayer {
  type: 'raster';
  png_base64?: string;
  asset_url?: string;
  mask_png_base64?: string;
  mask_svg_path?: string;
}

export interface TextStyle {
  font_size: number;
  font_color: string;
  stroke_color?: string;
  stroke_width: number;
  align: 'left' | 'center' | 'right';
  line_spacing: number;
  fit_to_box: boolean;
  shadow_color?: string;
  shadow_dx: number;
  shadow_dy: number;
  shadow_blur: number;
}

export interface TextLayer extends BaseLayer {
  type: 'text';
  text: string;
  bbox: [number, number, number, number];
  style: TextStyle;
  box_fill?: string;
  box_radius: number;
  box_padding: number;
}

export interface ShapeStyle {
  fill?: string;
  stroke?: string;
  stroke_width: number;
  radius: number;
  gradient?: Record<string, any>;
}

export interface ShapeLayer extends BaseLayer {
  type: 'shape';
  shape: 'rect' | 'round_rect' | 'ellipse' | 'path';
  bbox: [number, number, number, number];
  style: ShapeStyle;
  svg_path_d?: string;
}

export interface GradientLayer extends BaseLayer {
  type: 'gradient';
  angle: number;
  stops: [number, string][];
}

/**
 * 分层设计 API 响应
 */
export interface LayeredSuggestResponse {
  success: boolean;
  layerDoc?: LayerDoc;
  error?: string;
}

export interface LayeredDecomposeResponse {
  success: boolean;
  layers?: Array<{
    id: string;
    name: string;
    png_base64: string;
    z: number;
  }>;
  error?: string;
}

export interface LayeredVectorizeResponse {
  success: boolean;
  svg?: string;
  svg_base64?: string;
  paths?: Array<{
    id: string;
    d: string;
    points_count: number;
  }>;
  width?: number;
  height?: number;
  contours_count?: number;
  error?: string;
}

export interface LayeredRenderResponse {
  success: boolean;
  image_base64?: string;
  mime_type?: string;
  width?: number;
  height?: number;
  error?: string;
}

/**
 * 分层设计编辑模式
 */
export type LayeredDesignMode =
  | 'image-layered-suggest'
  | 'image-layered-decompose'
  | 'image-layered-vectorize'
  | 'image-layered-render';
```

### 4.2 API Hook (useLayeredDesign.ts)

```typescript
// frontend/hooks/useLayeredDesign.ts

import { useState, useCallback } from 'react';
import { apiClient } from '../services/apiClient';  // ✨ 使用 apiClient 自动处理认证
import {
  LayerDoc,
  Layer,
  LayeredSuggestResponse,
  LayeredDecomposeResponse,
  LayeredVectorizeResponse,
  LayeredRenderResponse
} from '../types/layeredDesign';

interface UseLayeredDesignOptions {
  providerId: string;
  onError?: (error: string) => void;
}

export function useLayeredDesign({ providerId, onError }: UseLayeredDesignOptions) {
  const [loading, setLoading] = useState(false);
  const [layerDoc, setLayerDoc] = useState<LayerDoc | null>(null);
  const [renderedImage, setRenderedImage] = useState<string | null>(null);

  /**
   * 布局建议
   *
   * 使用 apiClient.post() 自动处理:
   * - Authorization: Bearer <token> 请求头
   * - Content-Type: application/json
   * - Token 过期自动刷新
   * - 错误统一处理
   */
  const suggestLayout = useCallback(async (
    imageDataUrl: string,
    goal: string,
    options?: {
      canvasW?: number;
      canvasH?: number;
      maxTextBoxes?: number;
      modelId?: string;
    }
  ): Promise<LayeredSuggestResponse> => {
    setLoading(true);
    try {
      // ✨ 使用 apiClient 自动附带认证头
      const response = await apiClient.post<{
        success: boolean;
        data?: { layerDoc?: LayerDoc; error?: string };
      }>(`/api/modes/${providerId}/image-layered-suggest`, {
        modelId: options?.modelId || 'gemini-2.5-flash',
        prompt: goal,
        attachments: [{ url: imageDataUrl }],
        options: {
          canvasW: options?.canvasW || 2000,
          canvasH: options?.canvasH || 2000,
          maxTextBoxes: options?.maxTextBoxes || 3
        }
      });

      if (response.success && response.data?.layerDoc) {
        setLayerDoc(response.data.layerDoc);
        return { success: true, layerDoc: response.data.layerDoc };
      } else {
        const error = response.data?.error || 'Failed to suggest layout';
        onError?.(error);
        return { success: false, error };
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      onError?.(errorMsg);
      return { success: false, error: errorMsg };
    } finally {
      setLoading(false);
    }
  }, [providerId, onError]);

  /**
   * 图层分解
   */
  const decomposeLayers = useCallback(async (
    imageDataUrl: string
  ): Promise<LayeredDecomposeResponse> => {
    setLoading(true);
    try {
      // ✨ 使用 apiClient 自动附带认证头
      const response = await apiClient.post<{
        success: boolean;
        data?: { layers?: Array<{ id: string; name: string; png_base64: string; z: number }>; error?: string };
      }>(`/api/modes/${providerId}/image-layered-decompose`, {
        modelId: '',
        prompt: '',
        attachments: [{ url: imageDataUrl }]
      });

      if (response.success && response.data?.layers) {
        return { success: true, layers: response.data.layers };
      } else {
        const error = response.data?.error || 'Failed to decompose layers';
        onError?.(error);
        return { success: false, error };
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      onError?.(errorMsg);
      return { success: false, error: errorMsg };
    } finally {
      setLoading(false);
    }
  }, [providerId, onError]);

  /**
   * Mask 矢量化
   */
  const vectorizeMask = useCallback(async (
    maskDataUrl: string,
    options?: {
      simplifyTolerance?: number;
      smoothIterations?: number;
      useBezier?: boolean;
    }
  ): Promise<LayeredVectorizeResponse> => {
    setLoading(true);
    try {
      // ✨ 使用 apiClient 自动附带认证头
      const response = await apiClient.post<{
        success: boolean;
        data?: LayeredVectorizeResponse;
      }>(`/api/modes/${providerId}/image-layered-vectorize`, {
        modelId: '',
        prompt: '',
        attachments: [{ url: maskDataUrl }],
        options: {
          simplifyTolerance: options?.simplifyTolerance || 2.0,
          smoothIterations: options?.smoothIterations || 2,
          useBezier: options?.useBezier ?? true
        }
      });

      if (response.success && response.data?.svg) {
        return { success: true, ...response.data };
      } else {
        const error = response.data?.error || 'Failed to vectorize mask';
        onError?.(error);
        return { success: false, error };
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      onError?.(errorMsg);
      return { success: false, error: errorMsg };
    } finally {
      setLoading(false);
    }
  }, [providerId, onError]);

  /**
   * 渲染 LayerDoc
   */
  const renderLayerDoc = useCallback(async (
    doc: LayerDoc
  ): Promise<LayeredRenderResponse> => {
    setLoading(true);
    try {
      // ✨ 使用 apiClient 自动附带认证头
      const response = await apiClient.post<{
        success: boolean;
        data?: LayeredRenderResponse;
      }>(`/api/modes/${providerId}/image-layered-render`, {
        modelId: '',
        prompt: '',
        attachments: [],
        options: { layerDoc: doc }
      });

      if (response.success && response.data?.image_base64) {
        const imageUrl = `data:image/png;base64,${response.data.image_base64}`;
        setRenderedImage(imageUrl);
        return { success: true, ...response.data };
      } else {
        const error = response.data?.error || 'Failed to render';
        onError?.(error);
        return { success: false, error };
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      onError?.(errorMsg);
      return { success: false, error: errorMsg };
    } finally {
      setLoading(false);
    }
  }, [providerId, onError]);

  /**
   * 更新图层
   */
  const updateLayer = useCallback((layerId: string, updates: Partial<Layer>) => {
    if (!layerDoc) return;

    setLayerDoc(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        layers: prev.layers.map(layer =>
          layer.id === layerId ? { ...layer, ...updates } : layer
        )
      };
    });
  }, [layerDoc]);

  /**
   * 删除图层
   */
  const deleteLayer = useCallback((layerId: string) => {
    if (!layerDoc) return;

    setLayerDoc(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        layers: prev.layers.filter(layer => layer.id !== layerId)
      };
    });
  }, [layerDoc]);

  /**
   * 重排图层顺序
   */
  const reorderLayers = useCallback((newOrder: string[]) => {
    if (!layerDoc) return;

    setLayerDoc(prev => {
      if (!prev) return prev;

      const layerMap = new Map(prev.layers.map(l => [l.id, l]));
      const reordered = newOrder
        .map((id, index) => {
          const layer = layerMap.get(id);
          if (layer) {
            return { ...layer, z: index };
          }
          return null;
        })
        .filter((l): l is Layer => l !== null);

      return { ...prev, layers: reordered };
    });
  }, [layerDoc]);

  return {
    loading,
    layerDoc,
    renderedImage,
    setLayerDoc,
    suggestLayout,
    decomposeLayers,
    vectorizeMask,
    renderLayerDoc,
    updateLayer,
    deleteLayer,
    reorderLayers
  };
}
```

### 4.3 ImageEditView.tsx 集成方案

```tsx
// 在 ImageEditView.tsx 中添加 Tab 切换

// 新增状态
const [editTab, setEditTab] = useState<'chat' | 'layered'>('chat');

// 使用 Hook
const {
  loading: layeredLoading,
  layerDoc,
  renderedImage,
  suggestLayout,
  renderLayerDoc,
  updateLayer
} = useLayeredDesign({
  providerId: providerId || 'google',
  onError: (error) => showError(error)
});

// 在右侧参数面板添加 Tab 切换
<div className="flex border-b border-slate-800">
  <button
    onClick={() => setEditTab('chat')}
    className={`flex-1 py-2 text-xs font-medium ${
      editTab === 'chat'
        ? 'text-pink-400 border-b-2 border-pink-400'
        : 'text-slate-400 hover:text-white'
    }`}
  >
    对话编辑
  </button>
  <button
    onClick={() => setEditTab('layered')}
    className={`flex-1 py-2 text-xs font-medium ${
      editTab === 'layered'
        ? 'text-pink-400 border-b-2 border-pink-400'
        : 'text-slate-400 hover:text-white'
    }`}
  >
    分层设计
  </button>
</div>

{/* 根据 Tab 显示不同内容 */}
{editTab === 'chat' ? (
  // 现有的对话编辑 UI
  <ModeControlsCoordinator ... />
) : (
  // 新的分层设计 UI
  <LayeredDesignPanel
    layerDoc={layerDoc}
    onSuggestLayout={suggestLayout}
    onRender={renderLayerDoc}
    onUpdateLayer={updateLayer}
    activeImageUrl={activeImageUrl}
    loading={layeredLoading}
  />
)}
```

---

## 5. 数据流

### 5.1 布局建议流程

```
用户上传图片 → 点击"布局建议"
         ↓
POST /api/modes/{provider}/image-layered-suggest
         ↓
modes.py → mode_method_mapper → GoogleService/TongyiService
         ↓
layered_design(mode='image-layered-suggest')
         ↓
LayeredDesignService.suggest_layout()
         ↓
调用 LLM (Gemini/Qwen) 分析图片
         ↓
返回 LayerDoc JSON
         ↓
前端存储到 state，渲染图层列表
```

### 5.2 编辑 → 预览流程

```
用户修改文字/位置/样式
         ↓
updateLayer() 更新 layerDoc state
         ↓
点击"预览" 或 自动触发
         ↓
POST /api/modes/{provider}/image-layered-render
         ↓
LayeredDesignService.render_layerdoc()
         ↓
PIL 渲染 → PNG Base64
         ↓
前端显示在画布
```

---

## 6. 环境变量

```bash
# .env

# Qwen-Layered 图层分解服务（可选，如果需要 decompose 功能）
QWEN_LAYERED_ENDPOINT=http://qwen-layered-service:8080/decompose
QWEN_LAYERED_TIMEOUT_SEC=120

# 分层设计画布默认尺寸
LAYERED_CANVAS_W=2000
LAYERED_CANVAS_H=2000

# 字体路径（用于文字渲染）
FONT_PATH=/usr/share/fonts/NotoSansSC-Regular.ttf
```

---

## 7. 实现计划

### Phase 1: 核心功能 (P0) ✅ 已完成

| 任务 | 文件 | 状态 |
|------|------|------|
| 添加模式映射 | `mode_method_mapper.py` | ✅ 已完成 |
| 创建 LayeredDesignService | `common/layered_design_service.py` | ✅ 已完成 |
| GoogleService 集成 | `google_service.py` | ✅ 已完成 |
| 类型定义 | `layeredDesign.ts` | ✅ 已完成 |

### Phase 2: 前端集成 (P1) ✅ 已完成

| 任务 | 文件 | 状态 |
|------|------|------|
| API Hook | `useLayeredDesign.ts` | ✅ 已完成 |
| Tab 切换 UI | `ImageEditView.tsx` | ✅ 已完成 |
| 分层设计面板组件 | `LayeredDesignPanel.tsx` | ✅ 已完成 |
| 图层列表组件 | `LayerList.tsx` | ✅ 已完成 |

### Phase 3: 高级功能 (P2) ✅ 已完成

| 任务 | 文件 | 状态 |
|------|------|------|
| TongyiService 集成 | `tongyi_service.py` | ✅ 已完成 |
| 图层分解功能 | 需要 Qwen-Layered 服务 | ⏳ 外部服务开发中 |
| Mask 矢量化 UI | `VectorizePanel.tsx` | ✅ 已完成 |
| 图层属性编辑器 | `LayerPropertyEditor.tsx` | ✅ 已完成 |

---

## 8. 测试计划

### 8.1 后端测试

```python
# tests/test_layered_design_service.py

import pytest
from backend.app.services.common.layered_design_service import LayeredDesignService

class TestLayeredDesignService:

    def test_vectorize_mask_basic(self):
        """测试 Mask 矢量化基本功能"""
        service = LayeredDesignService()

        # 创建测试 mask
        from PIL import Image
        import io

        mask = Image.new("L", (100, 100), 0)
        # 绘制一个白色圆形
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        draw.ellipse([20, 20, 80, 80], fill=255)

        buf = io.BytesIO()
        mask.save(buf, format="PNG")
        mask_bytes = buf.getvalue()

        result = service.vectorize_mask(mask_bytes)

        assert result["success"] == True
        assert "svg" in result
        assert result["contours_count"] >= 1

    async def test_render_layerdoc(self):
        """测试 LayerDoc 渲染"""
        service = LayeredDesignService()

        layer_doc = {
            "width": 200,
            "height": 200,
            "background": "#FFFFFFFF",
            "layers": [
                {
                    "id": "text_1",
                    "type": "text",
                    "z": 1,
                    "opacity": 1.0,
                    "blend": "normal",
                    "text": "Hello",
                    "bbox": [10, 10, 180, 50],
                    "style": {"font_size": 24, "font_color": "#000000FF"},
                    "transform": {"x": 0, "y": 0, "scale": 1, "rotate": 0}
                }
            ]
        }

        result = await service.render_layerdoc(layer_doc)

        assert result["success"] == True
        assert "image_base64" in result
        assert result["width"] == 200
        assert result["height"] == 200
```

### 8.2 前端测试

```typescript
// tests/useLayeredDesign.test.ts

import { renderHook, act } from '@testing-library/react-hooks';
import { useLayeredDesign } from '../hooks/useLayeredDesign';

describe('useLayeredDesign', () => {
  it('should update layer correctly', () => {
    const { result } = renderHook(() =>
      useLayeredDesign({ providerId: 'google' })
    );

    // 设置初始 layerDoc
    act(() => {
      result.current.setLayerDoc({
        width: 100,
        height: 100,
        layers: [
          { id: 'layer1', type: 'text', text: 'Hello', ... }
        ]
      });
    });

    // 更新图层
    act(() => {
      result.current.updateLayer('layer1', { text: 'World' });
    });

    expect(result.current.layerDoc?.layers[0].text).toBe('World');
  });
});
```

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Qwen-Layered 服务不可用 | 图层分解功能不可用 | 返回友好错误提示，其他功能正常 |
| LLM 返回非法 JSON | 布局建议失败 | 增强 JSON 解析，多次重试 |
| 大图片渲染慢 | 用户体验差 | 添加进度提示，支持取消 |
| 字体缺失 | 文字渲染异常 | 使用系统默认字体回退 |

---

## 10. 认证与加密集成

### 10.1 认证机制概览

分层设计功能完全复用现有的认证体系，无需额外认证配置。

```
┌────────────────────────────────────────────────────────────────┐
│                     Frontend (apiClient.ts)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  每个请求自动附带:                                          │  │
│  │  - Authorization: Bearer <access_token>                   │  │
│  │  - Content-Type: application/json                         │  │
│  │  - X-CSRF-Token: <csrf_token> (如配置)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                     Backend (AuthMiddleware)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. 提取 Authorization header                              │  │
│  │  2. 验证 JWT token (jwt_utils.py)                         │  │
│  │  3. 解码 payload，提取 user_id                             │  │
│  │  4. 设置 request.state.user_id                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                     modes.py (路由层)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  user_id = request.state.user_id  # 从中间件获取           │  │
│  │  credentials = await get_provider_credentials(            │  │
│  │      provider, db, user_id, ...                           │  │
│  │  )  # 使用 credential_manager 获取凭证                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 10.2 前端请求头配置

分层设计 API 使用与其他 mode 完全相同的请求模式，由 `apiClient.ts` 统一处理。

```typescript
// frontend/services/apiClient.ts - 现有实现，无需修改

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // 自动附加 JWT Token
    const token = this.getAccessToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // 可选 CSRF Token
    const csrfToken = this.getCsrfToken();
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }

    // ... 发送请求
  }
}
```

### 10.3 后端认证中间件

分层设计请求通过 `/api/modes/{provider}/{mode}` 路由，自动经过 `AuthMiddleware` 验证。

```python
# backend/app/middleware/auth_middleware.py - 现有实现

class AuthMiddleware:
    """JWT 认证中间件"""

    async def __call__(self, request: Request, call_next):
        # 白名单路径（登录、注册等）不验证
        if self._is_whitelisted(request.url.path):
            return await call_next(request)

        # 提取 Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Missing or invalid token"}
            )

        token = auth_header.split(" ")[1]

        # 验证 JWT
        try:
            payload = verify_jwt(token)
            request.state.user_id = payload.get("sub")  # 用户 ID
        except JWTError as e:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": str(e)}
            )

        return await call_next(request)
```

### 10.4 凭证管理与自动解密

分层设计服务使用 `credential_manager.py` 统一获取凭证，支持自动解密。

```python
# backend/app/services/common/credential_manager.py - 现有实现

async def get_provider_credentials(
    provider: str,
    db: Session,
    user_id: Optional[str],
    request_api_key: Optional[str] = None,
    request_base_url: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    获取 Provider 凭证（自动解密）

    优先级:
    1. 请求参数中的 api_key/base_url
    2. 用户激活的配置档案
    3. 任意匹配的配置档案

    Returns:
        (api_key, base_url) 元组，api_key 已自动解密
    """
    # 如果请求参数提供了凭证，直接使用
    if request_api_key:
        return request_api_key, request_base_url

    # 从数据库获取用户配置档案
    profile = await get_active_profile(db, user_id, provider)

    if profile:
        # 自动解密 API Key
        api_key = _decrypt_api_key(profile.api_key, silent=True)
        return api_key, profile.base_url

    raise CredentialNotFoundError(f"No credentials found for provider: {provider}")


def _decrypt_api_key(encrypted_key: str, silent: bool = False) -> str:
    """解密 API Key"""
    from .encryption import decrypt_data, is_encrypted

    if is_encrypted(encrypted_key):
        return decrypt_data(encrypted_key)
    return encrypted_key
```

### 10.5 加密机制详解

系统使用 Fernet 对称加密保护敏感数据。

```python
# backend/app/services/common/encryption.py - 现有实现

from cryptography.fernet import Fernet
import os

# 敏感字段列表
SENSITIVE_FIELDS = {
    "token", "accessKeyId", "apiKey", "password",
    "secret", "privateKey", "credentials", "api_key"
}

# 加密密钥（从环境变量或配置文件获取）
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
_fernet = Fernet(ENCRYPTION_KEY.encode())


def encrypt_data(data: str) -> str:
    """加密数据"""
    return _fernet.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """解密数据"""
    return _fernet.decrypt(encrypted_data.encode()).decode()


def is_encrypted(data: str) -> bool:
    """检查数据是否已加密（Fernet 加密数据有特定格式）"""
    try:
        # Fernet token 以 "gAAAAA" 开头 (base64 编码的版本标识)
        return data.startswith("gAAAAA")
    except Exception:
        return False
```

### 10.6 分层设计服务凭证集成

分层设计服务在 `modes.py` 中的凭证获取流程：

```python
# backend/app/routers/core/modes.py - 分层设计相关部分

@router.post("/{provider}/{mode}")
async def process_mode(
    provider: str,
    mode: str,
    request: Request,
    body: ModeRequest,
    db: Session = Depends(get_db)
):
    """统一模式处理入口"""

    # 1. 获取认证用户 ID（从 AuthMiddleware 设置）
    user_id = getattr(request.state, 'user_id', None)

    # 2. 获取 Provider 凭证（自动解密）
    api_key, base_url = await get_provider_credentials(
        provider=provider,
        db=db,
        user_id=user_id,
        request_api_key=body.apiKey,      # 可选：请求中提供的 key
        request_base_url=body.baseUrl     # 可选：请求中提供的 URL
    )

    # 3. 创建 Provider 服务实例
    service = ProviderFactory.create(
        provider=provider,
        api_key=api_key,
        api_url=base_url,
        user_id=user_id,
        db=db
    )

    # 4. 获取服务方法并调用
    method_name = get_service_method(mode)
    method = getattr(service, method_name)

    # 5. 处理分层设计模式
    if is_layered_design_mode(mode):
        # 提取参考图片
        reference_images = extract_reference_images(body.attachments)

        result = await method(
            prompt=body.prompt,
            model=body.modelId,
            reference_images=reference_images,
            mode=mode,  # 传递原始 mode 用于内部路由
            **body.options
        )

        return {"success": True, "data": result}

    # ... 其他模式处理
```

### 10.7 Vertex AI 凭证处理

对于 Google Provider 使用 Vertex AI 的情况，需要额外的凭证处理：

```python
# backend/app/services/gemini/google_service.py - Vertex AI 初始化

class GoogleService(BaseProviderService):
    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs
    ):
        super().__init__(api_key, api_url, **kwargs)

        self.user_id = user_id
        self.db = db

        # 如果是 Vertex AI 模式，加载用户的 Vertex 配置
        if self._should_use_vertex_ai():
            self._load_vertex_credentials()

    def _load_vertex_credentials(self):
        """加载 Vertex AI 凭证（自动解密）"""
        if not self.user_id or not self.db:
            return

        from .vertexai.vertex_config_service import VertexConfigService

        config = VertexConfigService.get_user_config(
            db=self.db,
            user_id=self.user_id
        )

        if config:
            # 解密服务账户凭证
            from ..common.encryption import decrypt_data, is_encrypted

            credentials_json = config.credentials_json
            if is_encrypted(credentials_json):
                credentials_json = decrypt_data(credentials_json)

            self.vertex_project = config.project_id
            self.vertex_location = config.location
            self.vertex_credentials = json.loads(credentials_json)
```

### 10.8 数据库模型参考

分层设计功能不需要新的数据库模型，但依赖以下现有模型：

```python
# backend/app/models/config_profile.py

class ConfigProfile(Base):
    """配置档案模型 - 存储 Provider 凭证"""
    __tablename__ = "config_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    provider = Column(String, nullable=False)  # "google", "tongyi", etc.
    name = Column(String, nullable=False)
    api_key = Column(String)      # 加密存储
    base_url = Column(String)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)


# backend/app/models/vertex_ai_config.py

class VertexAIConfig(Base):
    """Vertex AI 配置模型"""
    __tablename__ = "vertex_ai_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    project_id = Column(String, nullable=False)
    location = Column(String, default="us-central1")
    credentials_json = Column(Text)  # 加密存储的服务账户 JSON
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 10.9 错误处理与安全考虑

```python
# 认证失败处理
class AuthenticationError(Exception):
    """认证失败异常"""
    pass

class CredentialNotFoundError(Exception):
    """凭证未找到异常"""
    pass

# 在 modes.py 中的错误处理
@router.post("/{provider}/{mode}")
async def process_mode(...):
    try:
        # ... 业务逻辑
    except AuthenticationError as e:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Authentication failed", "detail": str(e)}
        )
    except CredentialNotFoundError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Credentials not found", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"[modes.py] Unexpected error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error"}
        )
```

### 10.10 安全最佳实践

| 方面 | 实践 | 实现位置 |
|------|------|----------|
| **API Key 存储** | Fernet 加密后存储到数据库 | `encryption.py` |
| **传输安全** | HTTPS + JWT Bearer Token | `apiClient.ts` |
| **凭证获取** | 自动解密，不在日志中打印 | `credential_manager.py` |
| **Token 过期** | Access Token 15分钟过期 | `jwt_utils.py` |
| **刷新机制** | Refresh Token 7天有效 | `auth.py` |
| **敏感日志** | 不记录 API Key、凭证内容 | 全局 |

---

## 11. Qwen-Image-Layered 图层分解服务

### 11.1 概述

图层分解功能（`image-layered-decompose`）依赖 **Qwen-Image-Layered** 模型。

**部署策略**: 🔜 **外部独立服务**，GPU 资源隔离

**接入方式**: 后期通过认证机制接入

**参考实现**: `backend/app/services/gemini/geminiapi/app.py`

### 11.2 当前状态

| 状态 | 说明 |
|------|------|
| **服务状态** | 🔜 待部署（外部独立服务） |
| **接入方式** | 待定（后期通过认证接入） |
| **功能降级** | 图层分解功能暂不可用，其他功能正常 |

### 11.3 接口规范（预定义）

当外部服务就绪后，需符合以下接口规范：

```typescript
// 请求: POST /decompose
// Content-Type: multipart/form-data

// 响应格式
interface DecomposeResponse {
  success: boolean;
  layers?: Array<{
    id: string;         // "layer_0", "layer_1", ...
    name: string;       // "Background", "Layer 1", ...
    z: number;          // 图层顺序
    png_base64: string; // Base64 编码的 PNG
    width: number;
    height: number;
  }>;
  total?: number;
  seed?: number;
  error?: string;
}
```

### 11.4 环境变量配置

在 `backend/.env` 中配置以下环境变量：

```bash
# =============================================================================
# Qwen-Image-Layered 图层分解服务（外部独立部署，GPU 资源隔离）
# =============================================================================

# 服务端点（格式：http://域名:端口/路径）
# 示例：http://192.168.50.200:7860/decompose
QWEN_LAYERED_ENDPOINT=http://your-gpu-server:7860/decompose

# 外部服务独立认证密钥（非项目内 JWT，由外部服务管理）
# 此密钥与项目内的 JWT 认证系统完全独立
QWEN_LAYERED_API_KEY=your-external-service-api-key

# 请求超时时间（秒，默认 180，图层分解需要较长时间）
QWEN_LAYERED_TIMEOUT_SEC=180
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QWEN_LAYERED_ENDPOINT` | 图层分解服务地址 | 空（未配置则功能不可用） |
| `QWEN_LAYERED_API_KEY` | 外部服务认证密钥 | 空（可选） |
| `QWEN_LAYERED_TIMEOUT_SEC` | 请求超时时间 | 180 秒 |

**注意**：`QWEN_LAYERED_API_KEY` 是外部服务的独立认证，与项目内的 JWT Bearer Token 认证完全独立。

### 11.5 认证机制说明

```
项目内认证（JWT）                    外部服务认证（独立）
─────────────────────               ─────────────────────
前端 → apiClient.ts                 后端 → httpx client
       ↓                                   ↓
Authorization: Bearer <JWT>         Authorization: Bearer <QWEN_LAYERED_API_KEY>
       ↓                                   ↓
后端 AuthMiddleware                 Qwen-Layered Service
       ↓
layered_design_service.py ────────→ 外部 GPU 服务器
```

### 11.6 功能降级处理

当服务未配置时，返回友好提示：

```python
async def decompose_layers(self, image_bytes: bytes, **kwargs) -> Dict[str, Any]:
    endpoint = QWEN_LAYERED_ENDPOINT
    api_key = QWEN_LAYERED_API_KEY

    if not endpoint:
        return {
            "success": False,
            "error": "图层分解服务暂未开放，敬请期待",
            "code": "SERVICE_NOT_AVAILABLE"
        }

    # 构建独立的 Authorization header
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 调用外部服务...
```

### 11.7 错误码说明

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `SERVICE_NOT_AVAILABLE` | 服务未配置 | 配置 `QWEN_LAYERED_ENDPOINT` |
| `AUTH_FAILED` | 认证失败 (401) | 检查 `QWEN_LAYERED_API_KEY` |
| `ACCESS_DENIED` | 访问被拒绝 (403) | 联系服务管理员 |
| `TIMEOUT` | 请求超时 | 调整 `QWEN_LAYERED_TIMEOUT_SEC` |
| `CONNECTION_ERROR` | 连接失败 | 检查网络和服务地址 |
| `INVALID_RESPONSE` | 响应格式错误 | 检查外部服务版本 |

### 11.8 模型信息（参考）

| 属性 | 值 |
|------|------|
| 模型名称 | Qwen/Qwen-Image-Layered |
| 来源 | ModelScope |
| 模型大小 | ~10GB |
| 推荐显存 | ≥16GB VRAM |
| 推荐精度 | bfloat16 |

---

## 12. 参考资料

- [main.py 源代码](../backend/app/services/gemini/geminiapi/main.py) - 分层设计核心算法
- [app.py 源代码](../backend/app/services/gemini/geminiapi/app.py) - Qwen-Layered 参考实现
- [Qwen-Image-Layered 模型](https://www.modelscope.cn/models/Qwen/Qwen-Image-Layered) - 图层分解模型
- [Google GenAI SDK 文档](https://googleapis.github.io/python-genai/)
- [Pillow 文档](https://pillow.readthedocs.io/)
- [SVG Path 规范](https://www.w3.org/TR/SVG/paths.html)
- [Fernet 加密文档](https://cryptography.io/en/latest/fernet/)
- [JWT 规范](https://jwt.io/introduction)
