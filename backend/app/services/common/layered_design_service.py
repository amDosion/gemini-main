"""
分层设计服务 - Provider 无关的共享服务

从 main.py 提取的核心功能，支持跨 Provider 使用。

功能:
- suggest_layout: 布局建议（需要 LLM）
- decompose_layers: 图层分解（外部服务，待接入）
- vectorize_mask: Mask PNG → SVG（纯算法）
- render_layerdoc: LayerDoc → PNG（纯算法）
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
QWEN_LAYERED_API_KEY = os.getenv("QWEN_LAYERED_API_KEY", "").strip()
QWEN_LAYERED_TIMEOUT_SEC = int(os.getenv("QWEN_LAYERED_TIMEOUT_SEC", "180"))
DEFAULT_CANVAS_W = int(os.getenv("LAYERED_CANVAS_W", "2000"))
DEFAULT_CANVAS_H = int(os.getenv("LAYERED_CANVAS_H", "2000"))
FONT_PATH = os.getenv("FONT_PATH", "")

# Vectorize 默认参数
DEFAULT_SIMPLIFY_TOLERANCE = float(os.getenv("SIMPLIFY_TOLERANCE", "2.0"))
DEFAULT_SMOOTH_ITERATIONS = int(os.getenv("SMOOTH_ITERATIONS", "2"))


# =========================
# Utility Functions
# =========================
def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("utf-8"))


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@lru_cache(maxsize=128)
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载字体，带 LRU 缓存"""
    if FONT_PATH and os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _rgba_tuple(color: str) -> Tuple[int, int, int, int]:
    """解析颜色字符串 #RRGGBB 或 #RRGGBBAA"""
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


def _apply_opacity_rgba(img: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return img
    opacity = _clamp01(opacity)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img).astype(np.float32)
    arr[..., 3] = arr[..., 3] * opacity
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def _extract_json_from_llm_response(text: str) -> str:
    """从 LLM 响应中提取 JSON"""
    text = text.strip()

    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1]

    return text


def _linear_gradient_rgba(
    w: int,
    h: int,
    angle_deg: float,
    stops: List[Tuple[float, Tuple[int, int, int, int]]],
) -> Image.Image:
    """简单线性渐变"""
    angle = np.deg2rad(angle_deg)
    dx, dy = np.cos(angle), np.sin(angle)

    xs = np.linspace(-1, 1, w, dtype=np.float32)
    ys = np.linspace(-1, 1, h, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)
    T = X * dx + Y * dy
    T = (T - T.min()) / max(1e-6, (T.max() - T.min()))

    stops_sorted = sorted(stops, key=lambda x: x[0])
    ts = [t for t, _ in stops_sorted]
    cs = [c for _, c in stops_sorted]

    out = np.zeros((h, w, 4), dtype=np.float32)
    for i in range(len(ts) - 1):
        t0, t1 = ts[i], ts[i + 1]
        c0, c1 = np.array(cs[i], dtype=np.float32), np.array(cs[i + 1], dtype=np.float32)
        mask = (T >= t0) & (T <= t1)
        if not np.any(mask):
            continue
        alpha = (T[mask] - t0) / max(1e-6, (t1 - t0))
        out[mask] = (1 - alpha)[:, None] * c0 + alpha[:, None] * c1

    out[T < ts[0]] = np.array(cs[0], dtype=np.float32)
    out[T > ts[-1]] = np.array(cs[-1], dtype=np.float32)

    return Image.fromarray(out.astype(np.uint8), mode="RGBA")


# =========================
# Contour & Vectorization Utilities
# =========================
def _find_contours_from_mask(
    mask: np.ndarray, threshold: int = 128
) -> List[List[Tuple[int, int]]]:
    """从二值化 mask 中提取轮廓点（Moore 邻域追踪算法）"""
    binary = (mask > threshold).astype(np.uint8)
    h, w = binary.shape
    visited = np.zeros((h, w), dtype=bool)
    contours = []

    directions = [
        (0, 1), (1, 1), (1, 0), (1, -1),
        (0, -1), (-1, -1), (-1, 0), (-1, 1)
    ]

    def is_valid(y: int, x: int) -> bool:
        return 0 <= y < h and 0 <= x < w

    def is_edge(y: int, x: int) -> bool:
        if not is_valid(y, x) or binary[y, x] == 0:
            return False
        for dy, dx in directions:
            ny, nx = y + dy, x + dx
            if not is_valid(ny, nx) or binary[ny, nx] == 0:
                return True
        return False

    def trace_contour(start_y: int, start_x: int) -> List[Tuple[int, int]]:
        contour = [(start_x, start_y)]
        visited[start_y, start_x] = True

        start_dir = 0
        for i, (dy, dx) in enumerate(directions):
            ny, nx = start_y + dy, start_x + dx
            if not is_valid(ny, nx) or binary[ny, nx] == 0:
                start_dir = i
                break

        current_y, current_x = start_y, start_x
        search_dir = (start_dir + 5) % 8
        max_steps = h * w * 2
        steps = 0

        while steps < max_steps:
            steps += 1
            found = False

            for i in range(8):
                idx = (search_dir + i) % 8
                dy, dx = directions[idx]
                ny, nx = current_y + dy, current_x + dx

                if is_valid(ny, nx) and binary[ny, nx] == 1:
                    if ny == start_y and nx == start_x:
                        return contour

                    if not visited[ny, nx]:
                        visited[ny, nx] = True
                        contour.append((nx, ny))
                        current_y, current_x = ny, nx
                        search_dir = (idx + 5) % 8
                        found = True
                        break
                    elif len(contour) > 2:
                        return contour

            if not found:
                break

        return contour

    for y in range(h):
        for x in range(w):
            if binary[y, x] == 1 and not visited[y, x] and is_edge(y, x):
                if x == 0 or binary[y, x - 1] == 0:
                    contour = trace_contour(y, x)
                    if len(contour) >= 3:
                        contours.append(contour)

    return contours


def _simplify_contour_rdp(
    points: List[Tuple[int, int]], tolerance: float
) -> List[Tuple[int, int]]:
    """Ramer-Douglas-Peucker 算法简化轮廓"""
    if len(points) < 3:
        return points

    def perpendicular_distance(
        point: Tuple[int, int],
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
    ) -> float:
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

    def rdp_recursive(
        points: List[Tuple[int, int]], start: int, end: int
    ) -> List[Tuple[int, int]]:
        if end - start < 2:
            return [points[start]]

        max_dist = 0.0
        max_idx = start

        for i in range(start + 1, end):
            dist = perpendicular_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > tolerance:
            left = rdp_recursive(points, start, max_idx)
            right = rdp_recursive(points, max_idx, end)
            return left + right
        else:
            return [points[start]]

    result = rdp_recursive(points, 0, len(points) - 1)
    result.append(points[-1])

    return result


def _smooth_contour(
    points: List[Tuple[int, int]], iterations: int = 2
) -> List[Tuple[float, float]]:
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


def _points_to_svg_path(
    points: List[Tuple[float, float]], closed: bool = True
) -> str:
    """将点列表转换为 SVG path d 属性"""
    if len(points) < 2:
        return ""

    d = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

    for x, y in points[1:]:
        d += f" L {x:.2f} {y:.2f}"

    if closed:
        d += " Z"

    return d


def _points_to_bezier_path(
    points: List[Tuple[float, float]], closed: bool = True, smoothness: float = 0.25
) -> str:
    """将点列表转换为平滑的贝塞尔曲线 SVG path"""
    if len(points) < 2:
        return ""

    if len(points) == 2:
        return f"M {points[0][0]:.2f} {points[0][1]:.2f} L {points[1][0]:.2f} {points[1][1]:.2f}" + (" Z" if closed else "")

    n = len(points)

    def get_control_points(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        d01 = math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2)
        d12 = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

        if d01 < 1e-6:
            d01 = 1e-6
        if d12 < 1e-6:
            d12 = 1e-6

        fa = smoothness * d01 / (d01 + d12)
        fb = smoothness * d12 / (d01 + d12)

        cp1 = (
            p1[0] - fa * (p2[0] - p0[0]),
            p1[1] - fa * (p2[1] - p0[1]),
        )
        cp2 = (
            p1[0] + fb * (p2[0] - p0[0]),
            p1[1] + fb * (p2[1] - p0[1]),
        )

        return cp1, cp2

    control_points = []
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        cp1, cp2 = get_control_points(p0, p1, p2)
        control_points.append((cp1, cp2))

    d = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

    for i in range(n - 1 if not closed else n):
        next_i = (i + 1) % n
        _, cp1 = control_points[i]
        cp2, _ = control_points[next_i]
        p = points[next_i]
        d += f" C {cp1[0]:.2f} {cp1[1]:.2f}, {cp2[0]:.2f} {cp2[1]:.2f}, {p[0]:.2f} {p[1]:.2f}"

    if closed:
        d += " Z"

    return d


def _contours_to_svg(
    contours: List[List[Tuple[float, float]]],
    width: int,
    height: int,
    use_bezier: bool = True,
    smoothness: float = 0.25,
) -> str:
    """将轮廓列表转换为完整的 SVG 字符串"""
    paths = []
    for i, contour in enumerate(contours):
        if len(contour) < 3:
            continue

        if use_bezier:
            d = _points_to_bezier_path(contour, closed=True, smoothness=smoothness)
        else:
            d = _points_to_svg_path(contour, closed=True)

        paths.append(f'  <path id="contour_{i}" d="{d}" fill="black" fill-rule="evenodd"/>')

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <g id="mask_paths">
{chr(10).join(paths)}
  </g>
</svg>'''

    return svg


# =========================
# Main Service Class
# =========================
class LayeredDesignService:
    """
    分层设计服务 - Provider 无关的核心功能

    功能：
    - suggest_layout: 布局建议（需要 LLM）
    - decompose_layers: 图层分解（外部服务，待接入）
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
            return await self.decompose_layers(
                image_bytes=image_data,
                layers=kwargs.get("layers", 4),
                seed=kwargs.get("seed", -1),
                prompt=prompt if prompt else None
            )

        elif mode == "image-layered-vectorize":
            return self.vectorize_mask(
                mask_bytes=image_data,
                simplify_tolerance=kwargs.get("simplifyTolerance", DEFAULT_SIMPLIFY_TOLERANCE),
                smooth_iterations=kwargs.get("smoothIterations", DEFAULT_SMOOTH_ITERATIONS),
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
            logger.warning("[LayeredDesignService] _extract_image_data: reference_images is empty")
            return None

        raw = reference_images.get("raw")
        if not raw:
            logger.warning(f"[LayeredDesignService] _extract_image_data: 'raw' not found, keys: {list(reference_images.keys())}")
            return None

        logger.info(f"[LayeredDesignService] _extract_image_data: raw type={type(raw).__name__}")

        if isinstance(raw, dict):
            logger.info(f"[LayeredDesignService] _extract_image_data: raw dict keys={list(raw.keys())}")
            raw = raw.get("url") or raw.get("data")
            logger.info(f"[LayeredDesignService] _extract_image_data: extracted url/data type={type(raw).__name__ if raw else 'None'}")

        if isinstance(raw, str):
            if raw.startswith("data:"):
                logger.info(f"[LayeredDesignService] _extract_image_data: data URL, length={len(raw)}")
                base64_str = raw.split(",", 1)[1] if "," in raw else raw
                return base64.b64decode(base64_str)
            elif raw.startswith("http"):
                # HTTP URL - 需要下载图片
                logger.warning(f"[LayeredDesignService] _extract_image_data: HTTP URL not supported yet: {raw[:100]}...")
                return None
            else:
                # 可能是纯 base64 字符串
                logger.info(f"[LayeredDesignService] _extract_image_data: trying base64 decode, length={len(raw)}")
                try:
                    return base64.b64decode(raw)
                except Exception as e:
                    logger.error(f"[LayeredDesignService] _extract_image_data: base64 decode failed: {e}")
                    return None

        elif isinstance(raw, bytes):
            logger.info(f"[LayeredDesignService] _extract_image_data: bytes data, length={len(raw)}")
            return raw

        logger.warning(f"[LayeredDesignService] _extract_image_data: unsupported type: {type(raw).__name__}")
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
            response_text = await self._call_llm_with_image(prompt, image_bytes)
            json_text = _extract_json_from_llm_response(response_text)
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
        """调用 LLM 进行图片分析"""
        client_type = type(self.llm_client).__name__

        if "Client" in client_type or hasattr(self.llm_client, "models"):
            return await self._call_google_llm(prompt, image_bytes)
        elif hasattr(self.llm_client, "chat") or hasattr(self.llm_client, "stream_chat"):
            return await self._call_tongyi_llm(prompt, image_bytes)
        else:
            raise ValueError(f"Unsupported LLM client type: {client_type}")

    async def _call_google_llm(self, prompt: str, image_bytes: bytes) -> str:
        """调用 Google Gemini LLM"""
        try:
            from google.genai import types as genai_types
        except ImportError:
            genai_types = None

        contents = [prompt]

        if genai_types:
            contents.append(genai_types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png"
            ))

        if hasattr(self.llm_client, "aio"):
            response = await self.llm_client.aio.models.generate_content(
                model=self.llm_model,
                contents=contents,
                config={"temperature": 0.25, "max_output_tokens": 4096}
            )
        else:
            response = self.llm_client.models.generate_content(
                model=self.llm_model,
                contents=contents,
                config={"temperature": 0.25, "max_output_tokens": 4096}
            )

        return getattr(response, "text", "") or ""

    async def _call_tongyi_llm(self, prompt: str, image_bytes: bytes) -> str:
        """调用 Tongyi Qwen LLM"""
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{image_base64}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_url},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        response = await self.llm_client.chat(
            messages=messages,
            model=self.llm_model or "qwen-vl-max"
        )

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

    # =========================
    # 2. 图层分解 (外部服务)
    # =========================
    async def decompose_layers(
        self,
        image_bytes: bytes,
        layers: int = 4,
        seed: int = -1,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        图层分解 - 调用外部 Qwen-Image-Layered 服务

        外部服务配置（.env）：
        - QWEN_LAYERED_ENDPOINT: 服务地址，如 http://192.168.1.100:7860/decompose
        - QWEN_LAYERED_API_KEY: 独立认证密钥（非项目内 JWT）
        - QWEN_LAYERED_TIMEOUT_SEC: 超时时间（默认 180 秒）

        Args:
            image_bytes: 输入图片字节数据
            layers: 分解图层数 (2-10)
            seed: 随机种子 (-1 表示随机)
            prompt: 可选提示词（描述图片内容）

        Returns:
            包含图层列表的字典:
            {
                "success": True,
                "layers": [...],
                "total": 4,
                "seed": 12345
            }
        """
        endpoint = QWEN_LAYERED_ENDPOINT
        api_key = QWEN_LAYERED_API_KEY

        if not endpoint:
            return {
                "success": False,
                "error": "图层分解服务暂未开放，敬请期待",
                "code": "SERVICE_NOT_AVAILABLE"
            }

        if not image_bytes:
            return {
                "success": False,
                "error": "decompose_layers requires image data"
            }

        http_client = self.http_client
        should_close = False

        if not http_client:
            http_client = httpx.AsyncClient(timeout=httpx.Timeout(float(QWEN_LAYERED_TIMEOUT_SEC)))
            should_close = True

        try:
            # 构建请求头 - 独立的 Authorization（非项目内 JWT）
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
                logger.debug("[LayeredDesignService] Using external service Authorization")

            # 构建表单数据
            files = {
                "image": ("image.png", image_bytes, "image/png")
            }
            data = {
                "layers": str(layers),
                "seed": str(seed),
            }
            if prompt:
                data["prompt"] = prompt

            logger.info(f"[LayeredDesignService] Calling decompose service: {endpoint}")
            logger.info(f"[LayeredDesignService] Parameters: layers={layers}, seed={seed}, has_prompt={bool(prompt)}")

            response = await http_client.post(
                endpoint,
                headers=headers,
                files=files,
                data=data,
                timeout=QWEN_LAYERED_TIMEOUT_SEC
            )

            # 处理认证错误
            if response.status_code == 401:
                logger.error("[LayeredDesignService] External service authentication failed")
                return {
                    "success": False,
                    "error": "图层分解服务认证失败，请检查 QWEN_LAYERED_API_KEY 配置",
                    "code": "AUTH_FAILED"
                }

            if response.status_code == 403:
                logger.error("[LayeredDesignService] External service access forbidden")
                return {
                    "success": False,
                    "error": "图层分解服务访问被拒绝",
                    "code": "ACCESS_DENIED"
                }

            if response.status_code != 200:
                error_text = response.text[:500] if response.text else "Unknown error"
                return {
                    "success": False,
                    "error": f"图层分解服务错误: {response.status_code} - {error_text}"
                }

            result = response.json()

            if result.get("success"):
                total = result.get("total", len(result.get("layers", [])))
                logger.info(f"[LayeredDesignService] decompose_layers: {total} layers generated")
                return result
            else:
                return {
                    "success": False,
                    "error": result.get("error", "图层分解失败")
                }

        except httpx.TimeoutException:
            logger.error(f"[LayeredDesignService] decompose timeout ({QWEN_LAYERED_TIMEOUT_SEC}s)")
            return {
                "success": False,
                "error": f"图层分解服务超时（{QWEN_LAYERED_TIMEOUT_SEC}秒），请稍后重试",
                "code": "TIMEOUT"
            }
        except httpx.RequestError as e:
            logger.error(f"[LayeredDesignService] decompose request failed: {e}")
            return {
                "success": False,
                "error": f"无法连接图层分解服务: {str(e)}",
                "code": "CONNECTION_ERROR"
            }
        except json.JSONDecodeError as e:
            logger.error(f"[LayeredDesignService] Invalid JSON response: {e}")
            return {
                "success": False,
                "error": "图层分解服务返回无效数据",
                "code": "INVALID_RESPONSE"
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
        simplify_tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
        smooth_iterations: int = DEFAULT_SMOOTH_ITERATIONS,
        use_bezier: bool = True,
        bezier_smoothness: float = 0.25,
        threshold: int = 128,
        blur_radius: float = 0.0
    ) -> Dict[str, Any]:
        """
        将 mask PNG 转换为可编辑的 SVG path

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
            mask_img = Image.open(io.BytesIO(mask_bytes))

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
            raw_contours = _find_contours_from_mask(mask_arr, threshold=threshold)

            # 简化和平滑
            processed_contours = []
            path_data = []

            for i, contour in enumerate(raw_contours):
                if len(contour) < 3:
                    continue

                simplified = _simplify_contour_rdp(contour, simplify_tolerance)
                if len(simplified) < 3:
                    continue

                smoothed = _smooth_contour(simplified, iterations=smooth_iterations)
                if len(smoothed) < 3:
                    continue

                processed_contours.append(smoothed)

                if use_bezier:
                    d = _points_to_bezier_path(smoothed, closed=True, smoothness=bezier_smoothness)
                else:
                    d = _points_to_svg_path(smoothed, closed=True)

                path_data.append({
                    "id": f"contour_{i}",
                    "d": d,
                    "points_count": len(smoothed)
                })

            svg = _contours_to_svg(
                processed_contours,
                width=w,
                height=h,
                use_bezier=use_bezier,
                smoothness=bezier_smoothness
            )

            svg_bytes = svg.encode("utf-8")
            svg_base64 = base64.b64encode(svg_bytes).decode("utf-8")

            logger.info(f"[LayeredDesignService] vectorize_mask: {len(processed_contours)} contours")

            return {
                "success": True,
                "svg": svg,
                "svg_base64": svg_base64,
                "paths": path_data,
                "width": w,
                "height": h,
                "contours_count": len(processed_contours)
            }

        except Exception as e:
            logger.error(f"[LayeredDesignService] vectorize_mask failed: {e}")
            return {
                "success": False,
                "error": f"Vectorization failed: {str(e)}"
            }

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
            img = self._render_layerdoc_impl(layer_doc)

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
        """渲染 LayerDoc 到 PIL Image"""
        width = doc.get("width", DEFAULT_CANVAS_W)
        height = doc.get("height", DEFAULT_CANVAS_H)
        background = doc.get("background")
        layers = doc.get("layers", [])

        if background:
            canvas = Image.new("RGBA", (width, height), _rgba_tuple(background))
        else:
            canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))

        layers_sorted = sorted(layers, key=lambda l: l.get("z", 0))

        for layer in layers_sorted:
            layer_type = layer.get("type")
            opacity = layer.get("opacity", 1.0)

            if layer_type == "gradient":
                self._render_gradient_layer(canvas, layer, opacity)
            elif layer_type == "shape":
                self._render_shape_layer(canvas, layer, opacity)
            elif layer_type == "text":
                self._render_text_layer(canvas, layer, opacity)
            elif layer_type == "raster":
                self._render_raster_layer(canvas, layer, opacity)

        return canvas

    def _render_gradient_layer(self, canvas: Image.Image, layer: Dict[str, Any], opacity: float):
        """渲染渐变图层"""
        angle = layer.get("angle", 0)
        stops_raw = layer.get("stops", [])

        if not stops_raw:
            return

        stops = []
        for stop in stops_raw:
            if isinstance(stop, list) and len(stop) >= 2:
                t, color = stop[0], stop[1]
                stops.append((t, _rgba_tuple(color)))
            elif isinstance(stop, dict):
                t = stop.get("position", 0)
                color = stop.get("color", "#FFFFFFFF")
                stops.append((t, _rgba_tuple(color)))

        if len(stops) < 2:
            color = _rgba_tuple(stops_raw[0][1] if isinstance(stops_raw[0], list) else "#FFFFFFFF")
            grad = Image.new("RGBA", canvas.size, color)
        else:
            grad = _linear_gradient_rgba(canvas.width, canvas.height, angle, stops)

        if opacity < 1.0:
            grad = _apply_opacity_rgba(grad, opacity)

        canvas.alpha_composite(grad)

    def _render_shape_layer(self, canvas: Image.Image, layer: Dict[str, Any], opacity: float):
        """渲染形状图层"""
        bbox = layer.get("bbox", [0, 0, 100, 100])
        x, y, w, h = bbox
        style = layer.get("style", {})

        shape_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shape_img)

        fill = style.get("fill")
        if fill:
            fill_color = _rgba_tuple(fill)
            shape_type = layer.get("shape", "rect")
            radius = style.get("radius", 0)

            if shape_type == "round_rect":
                draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=fill_color)
            elif shape_type == "ellipse":
                draw.ellipse([0, 0, w, h], fill=fill_color)
            else:
                draw.rectangle([0, 0, w, h], fill=fill_color)

        if opacity < 1.0:
            shape_img = _apply_opacity_rgba(shape_img, opacity)

        canvas.alpha_composite(shape_img, dest=(x, y))

    def _render_text_layer(self, canvas: Image.Image, layer: Dict[str, Any], opacity: float):
        """渲染文字图层"""
        bbox = layer.get("bbox", [0, 0, 100, 50])
        x, y, w, h = bbox
        text = layer.get("text", "")
        style = layer.get("style", {})

        text_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_img)

        box_fill = layer.get("box_fill")
        if box_fill:
            box_radius = layer.get("box_radius", 0)
            fill_color = _rgba_tuple(box_fill)
            draw.rounded_rectangle([0, 0, w, h], radius=box_radius, fill=fill_color)

        font_size = style.get("font_size", 24)
        font_color = _rgba_tuple(style.get("font_color", "#000000FF"))

        try:
            font = _load_font(font_size)
        except Exception:
            font = ImageFont.load_default()

        padding = layer.get("box_padding", 10)
        draw.text((padding, padding), text, font=font, fill=font_color)

        if opacity < 1.0:
            text_img = _apply_opacity_rgba(text_img, opacity)

        canvas.alpha_composite(text_img, dest=(x, y))

    def _render_raster_layer(self, canvas: Image.Image, layer: Dict[str, Any], opacity: float):
        """渲染位图图层"""
        png_base64 = layer.get("png_base64")
        if png_base64:
            try:
                img_bytes = base64.b64decode(png_base64)
                img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

                transform = layer.get("transform", {})
                x = int(transform.get("x", 0))
                y = int(transform.get("y", 0))

                if opacity < 1.0:
                    img = _apply_opacity_rgba(img, opacity)

                canvas.alpha_composite(img, dest=(x, y))
            except Exception as e:
                logger.warning(f"[LayeredDesignService] Failed to render raster layer: {e}")
