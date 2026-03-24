# main.py
"""
Layered Design API (Vertex AI + Qwen-Layered)

完整修改版 v2.0.0
- 修复 Pydantic Union 类型歧义
- 字体 LRU 缓存
- 异步 HTTP 客户端 (httpx)
- Gemini JSON 解析增强
- 渲染异步化（预加载远程资源）
- 重试机制
- 新增 /v1/mask/vectorize：将 mask PNG 转换为可编辑 SVG path
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import os
import re
from functools import lru_cache
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union

import httpx
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Discriminator, Field, Tag, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from google import genai
from google.genai import types


# =========================
# Config
# =========================
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-4.0-generate-001")

HTTP_OPTIONS = types.HttpOptions(api_version=os.getenv("GENAI_API_VERSION", "v1"))

QWEN_LAYERED_ENDPOINT = os.getenv("QWEN_LAYERED_ENDPOINT", "").strip()
QWEN_LAYERED_TIMEOUT_SEC = int(os.getenv("QWEN_LAYERED_TIMEOUT_SEC", "120"))

DEFAULT_CANVAS_W = int(os.getenv("CANVAS_W", "2000"))
DEFAULT_CANVAS_H = int(os.getenv("CANVAS_H", "2000"))

# 字体：生产建议放一份 NotoSansSC/思源黑体到容器里
FONT_PATH = os.getenv("FONT_PATH", "")

# Vectorize 默认参数
DEFAULT_SIMPLIFY_TOLERANCE = float(os.getenv("SIMPLIFY_TOLERANCE", "2.0"))
DEFAULT_SMOOTH_ITERATIONS = int(os.getenv("SMOOTH_ITERATIONS", "2"))


# =========================
# Utilities - Basic
# =========================
def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("utf-8"))


def _guess_mime(filename: str) -> str:
    fn = (filename or "").lower()
    if fn.endswith(".png"):
        return "image/png"
    if fn.endswith(".webp"):
        return "image/webp"
    if fn.endswith(".jpg") or fn.endswith(".jpeg"):
        return "image/jpeg"
    return "image/png"


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@lru_cache(maxsize=128)
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载字体，带 LRU 缓存避免重复磁盘 IO"""
    if FONT_PATH and os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow < 10.0 不支持 size 参数
        return ImageFont.load_default()


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _rgba_tuple(color: str) -> Tuple[int, int, int, int]:
    """支持：#RRGGBB, #RRGGBBAA"""
    c = color.strip()
    if not c.startswith("#"):
        raise ValueError("Color must be hex like #RRGGBB or #RRGGBBAA")
    c = c[1:]
    if len(c) == 6:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (r, g, b, 255)
    if len(c) == 8:
        r, g, b, a = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16)
        return (r, g, b, a)
    raise ValueError("Unsupported hex color length")


def _apply_opacity_rgba(img: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return img
    opacity = _clamp01(opacity)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img).astype(np.float32)
    arr[..., 3] = arr[..., 3] * opacity
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def _paste_with_alpha(dst: Image.Image, src: Image.Image, xy: Tuple[int, int]) -> None:
    if src.mode != "RGBA":
        src = src.convert("RGBA")
    dst.alpha_composite(src, dest=xy)


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


def _extract_json_from_llm_response(text: str) -> str:
    """从 LLM 响应中提取 JSON，处理可能的 markdown 代码块包裹"""
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
        return text[first_brace : last_brace + 1]

    return text


# =========================
# Utilities - Contour & Vectorization
# =========================
def _find_contours_from_mask(
    mask: np.ndarray, threshold: int = 128
) -> List[List[Tuple[int, int]]]:
    """
    从二值化 mask 中提取轮廓点（类似 OpenCV findContours）。
    使用 Moore 邻域追踪算法。
    
    Args:
        mask: 2D numpy array (H, W), 灰度图
        threshold: 二值化阈值
    
    Returns:
        轮廓列表，每个轮廓是 (x, y) 点列表
    """
    binary = (mask > threshold).astype(np.uint8)
    h, w = binary.shape
    visited = np.zeros((h, w), dtype=bool)
    contours = []

    # Moore 邻域：8个方向，从右开始顺时针
    directions = [
        (0, 1), (1, 1), (1, 0), (1, -1),
        (0, -1), (-1, -1), (-1, 0), (-1, 1)
    ]

    def is_valid(y: int, x: int) -> bool:
        return 0 <= y < h and 0 <= x < w

    def is_edge(y: int, x: int) -> bool:
        """检查是否是边界像素（前景像素且相邻有背景）"""
        if not is_valid(y, x) or binary[y, x] == 0:
            return False
        for dy, dx in directions:
            ny, nx = y + dy, x + dx
            if not is_valid(ny, nx) or binary[ny, nx] == 0:
                return True
        return False

    def trace_contour(start_y: int, start_x: int) -> List[Tuple[int, int]]:
        """从起点追踪一个完整轮廓"""
        contour = [(start_x, start_y)]
        visited[start_y, start_x] = True
        
        # 找初始方向（第一个背景像素的方向）
        start_dir = 0
        for i, (dy, dx) in enumerate(directions):
            ny, nx = start_y + dy, start_x + dx
            if not is_valid(ny, nx) or binary[ny, nx] == 0:
                start_dir = i
                break
        
        current_y, current_x = start_y, start_x
        search_dir = (start_dir + 5) % 8  # 从背景方向的下一个开始搜索
        
        max_steps = h * w * 2  # 防止无限循环
        steps = 0
        
        while steps < max_steps:
            steps += 1
            found = False
            
            # 逆时针搜索 8 个方向
            for i in range(8):
                idx = (search_dir + i) % 8
                dy, dx = directions[idx]
                ny, nx = current_y + dy, current_x + dx
                
                if is_valid(ny, nx) and binary[ny, nx] == 1:
                    # 回到起点
                    if ny == start_y and nx == start_x:
                        return contour
                    
                    if not visited[ny, nx]:
                        visited[ny, nx] = True
                        contour.append((nx, ny))
                        current_y, current_x = ny, nx
                        # 下次从找到点的反方向+1开始搜索
                        search_dir = (idx + 5) % 8
                        found = True
                        break
                    elif len(contour) > 2:
                        # 如果已访问但轮廓足够长，可能是闭合了
                        return contour
            
            if not found:
                break
        
        return contour

    # 扫描找起点
    for y in range(h):
        for x in range(w):
            if binary[y, x] == 1 and not visited[y, x] and is_edge(y, x):
                # 检查是否是外轮廓起点（左边是背景或边界外）
                if x == 0 or binary[y, x - 1] == 0:
                    contour = trace_contour(y, x)
                    if len(contour) >= 3:  # 至少3个点才是有效轮廓
                        contours.append(contour)

    return contours


def _simplify_contour_rdp(
    points: List[Tuple[int, int]], tolerance: float
) -> List[Tuple[int, int]]:
    """
    Ramer-Douglas-Peucker 算法简化轮廓。
    
    Args:
        points: 轮廓点列表
        tolerance: 简化容差（像素）
    
    Returns:
        简化后的点列表
    """
    if len(points) < 3:
        return points

    def perpendicular_distance(
        point: Tuple[int, int],
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
    ) -> float:
        """计算点到线段的垂直距离"""
        x0, y0 = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            return math.sqrt((x0 - x1) ** 2 + (y0 - y1) ** 2)
        
        # 点到直线距离公式
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
    """
    平滑轮廓（Chaikin 角切算法）。
    
    Args:
        points: 轮廓点列表
        iterations: 平滑迭代次数
    
    Returns:
        平滑后的点列表（浮点坐标）
    """
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
            
            # Q = 3/4 * P0 + 1/4 * P1
            q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
            # R = 1/4 * P0 + 3/4 * P1
            r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
            
            new_pts.append(q)
            new_pts.append(r)
        
        pts = new_pts
    
    return pts


def _points_to_svg_path(
    points: List[Tuple[float, float]], closed: bool = True
) -> str:
    """
    将点列表转换为 SVG path d 属性。
    
    Args:
        points: 点列表 (x, y)
        closed: 是否闭合路径
    
    Returns:
        SVG path d 字符串
    """
    if len(points) < 2:
        return ""
    
    # 起点
    d = f"M {points[0][0]:.2f} {points[0][1]:.2f}"
    
    # 使用二次贝塞尔曲线连接
    if len(points) >= 3:
        # 计算控制点（相邻点的中点）
        for i in range(1, len(points)):
            x, y = points[i]
            d += f" L {x:.2f} {y:.2f}"
    else:
        for x, y in points[1:]:
            d += f" L {x:.2f} {y:.2f}"
    
    if closed:
        d += " Z"
    
    return d


def _points_to_bezier_path(
    points: List[Tuple[float, float]], closed: bool = True, smoothness: float = 0.25
) -> str:
    """
    将点列表转换为平滑的贝塞尔曲线 SVG path。
    
    Args:
        points: 点列表 (x, y)
        closed: 是否闭合路径
        smoothness: 平滑度 (0-0.5)
    
    Returns:
        SVG path d 字符串（使用三次贝塞尔曲线）
    """
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
        """计算贝塞尔曲线控制点"""
        d01 = math.sqrt((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2)
        d12 = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
        
        if d01 < 1e-6:
            d01 = 1e-6
        if d12 < 1e-6:
            d12 = 1e-6
        
        fa = smoothness * d01 / (d01 + d12)
        fb = smoothness * d12 / (d01 + d12)
        
        # 控制点
        cp1 = (
            p1[0] - fa * (p2[0] - p0[0]),
            p1[1] - fa * (p2[1] - p0[1]),
        )
        cp2 = (
            p1[0] + fb * (p2[0] - p0[0]),
            p1[1] + fb * (p2[1] - p0[1]),
        )
        
        return cp1, cp2
    
    # 计算所有控制点
    control_points = []
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        cp1, cp2 = get_control_points(p0, p1, p2)
        control_points.append((cp1, cp2))
    
    # 构建路径
    d = f"M {points[0][0]:.2f} {points[0][1]:.2f}"
    
    for i in range(n - 1 if not closed else n):
        next_i = (i + 1) % n
        
        # 当前点的出控制点
        _, cp1 = control_points[i]
        # 下一点的入控制点
        cp2, _ = control_points[next_i]
        # 下一点
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
    """
    将轮廓列表转换为完整的 SVG 字符串。
    
    Args:
        contours: 轮廓列表，每个轮廓是点列表
        width: 画布宽度
        height: 画布高度
        use_bezier: 是否使用贝塞尔曲线
        smoothness: 贝塞尔曲线平滑度
    
    Returns:
        完整的 SVG 字符串
    """
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


def vectorize_mask(
    mask_img: Image.Image,
    simplify_tolerance: float = 2.0,
    smooth_iterations: int = 2,
    use_bezier: bool = True,
    bezier_smoothness: float = 0.25,
    threshold: int = 128,
    blur_radius: float = 0.0,
) -> Dict[str, Any]:
    """
    将 mask PNG 转换为可编辑的 SVG path。
    
    这是"真正像 PS 那样编辑轮廓"的关键功能。
    
    Args:
        mask_img: PIL Image (灰度或 RGBA，使用 alpha 通道)
        simplify_tolerance: RDP 简化容差（像素）
        smooth_iterations: Chaikin 平滑迭代次数
        use_bezier: 是否输出贝塞尔曲线
        bezier_smoothness: 贝塞尔曲线平滑度 (0-0.5)
        threshold: 二值化阈值
        blur_radius: 预处理高斯模糊半径（减少噪点）
    
    Returns:
        {
            "svg": SVG 字符串,
            "paths": [{"id": str, "d": str, "points_count": int}, ...],
            "width": int,
            "height": int,
            "contours_count": int,
        }
    """
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
        
        # RDP 简化
        simplified = _simplify_contour_rdp(contour, simplify_tolerance)
        if len(simplified) < 3:
            continue
        
        # Chaikin 平滑
        smoothed = _smooth_contour(simplified, iterations=smooth_iterations)
        if len(smoothed) < 3:
            continue
        
        processed_contours.append(smoothed)
        
        # 生成 path d
        if use_bezier:
            d = _points_to_bezier_path(smoothed, closed=True, smoothness=bezier_smoothness)
        else:
            d = _points_to_svg_path(smoothed, closed=True)
        
        path_data.append({
            "id": f"contour_{i}",
            "d": d,
            "points_count": len(smoothed),
        })
    
    # 生成完整 SVG
    svg = _contours_to_svg(
        processed_contours,
        width=w,
        height=h,
        use_bezier=use_bezier,
        smoothness=bezier_smoothness,
    )
    
    return {
        "svg": svg,
        "paths": path_data,
        "width": w,
        "height": h,
        "contours_count": len(processed_contours),
    }


# =========================
# LayerDoc Schema
# =========================
BlendMode = Literal["normal", "multiply", "screen", "overlay"]


class Transform(BaseModel):
    x: float = 0
    y: float = 0
    scale: float = 1.0
    rotate: float = 0.0  # degrees
    anchor_x: float = 0.0  # 0..1
    anchor_y: float = 0.0  # 0..1


class BaseLayer(BaseModel):
    id: str
    name: Optional[str] = None
    type: str
    z: int = 0
    opacity: float = 1.0
    blend: BlendMode = "normal"
    transform: Transform = Field(default_factory=Transform)


class RasterLayer(BaseLayer):
    type: Literal["raster"]
    png_base64: Optional[str] = None
    asset_url: Optional[str] = None
    # 可选 mask：用于裁剪不规则形状（PNG alpha 或灰度）
    mask_png_base64: Optional[str] = None
    # 新增：可编辑的 SVG mask path（优先于 mask_png_base64）
    mask_svg_path: Optional[str] = None


class TextStyle(BaseModel):
    font_size: int = 64
    font_color: str = "#FFFFFFFF"
    stroke_color: Optional[str] = None
    stroke_width: int = 0
    align: Literal["left", "center", "right"] = "center"
    line_spacing: float = 1.15
    fit_to_box: bool = True
    shadow_color: Optional[str] = "#00000066"
    shadow_dx: int = 2
    shadow_dy: int = 2
    shadow_blur: int = 0


class TextLayer(BaseLayer):
    type: Literal["text"]
    text: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    style: TextStyle = Field(default_factory=TextStyle)
    box_fill: Optional[str] = None
    box_radius: int = 24
    box_padding: int = 24


class ShapeStyle(BaseModel):
    fill: Optional[str] = "#FFFFFFFF"
    stroke: Optional[str] = None
    stroke_width: int = 0
    radius: int = 24
    gradient: Optional[Dict[str, Any]] = None


class ShapeLayer(BaseLayer):
    type: Literal["shape"]
    shape: Literal["rect", "round_rect", "ellipse", "path"]
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    style: ShapeStyle = Field(default_factory=ShapeStyle)
    # 新增：自定义 SVG path（当 shape="path" 时使用）
    svg_path_d: Optional[str] = None


class GradientLayer(BaseLayer):
    type: Literal["gradient"]
    angle: float = 0.0
    stops: List[Tuple[float, str]] = Field(
        default_factory=lambda: [(0.0, "#FF0000FF"), (1.0, "#0000FFFF")]
    )


# 使用 Discriminator 解决 Pydantic Union 歧义
Layer = Annotated[
    Union[
        Annotated[RasterLayer, Tag("raster")],
        Annotated[TextLayer, Tag("text")],
        Annotated[ShapeLayer, Tag("shape")],
        Annotated[GradientLayer, Tag("gradient")],
    ],
    Discriminator("type"),
]


class LayerDoc(BaseModel):
    width: int = DEFAULT_CANVAS_W
    height: int = DEFAULT_CANVAS_H
    background: Optional[str] = None
    layers: List[Layer]


# =========================
# Request/Response Models
# =========================
class GenerateImageReq(BaseModel):
    prompt: str
    number_of_images: int = 1
    output_mime_type: str = "image/png"


class LayoutSuggestReq(BaseModel):
    locale: str = "zh-CN"
    goal: str = "生成一张适合电商附图的分层布局：底图无字；文字在矩形框内；可编辑；风格统一。"
    canvas_w: int = DEFAULT_CANVAS_W
    canvas_h: int = DEFAULT_CANVAS_H
    max_text_boxes: int = 3


class VectorizeResponse(BaseModel):
    """mask/vectorize 的响应模型"""
    svg: str
    svg_base64: str
    paths: List[Dict[str, Any]]
    width: int
    height: int
    contours_count: int


# =========================
# App Setup
# =========================
app = FastAPI(
    title="Layered Design API",
    description="分层图像设计 API，支持 Vertex AI (Gemini/Imagen)、Qwen-Layered 分层、SVG 矢量化",
    version="2.0.0",
)

_cors_origins = [o for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else ["*"],
    allow_credentials=bool(_cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")

    if project and location:
        client = genai.Client(
            vertexai=True, project=project, location=location, http_options=HTTP_OPTIONS
        )
    else:
        client = genai.Client(http_options=HTTP_OPTIONS)

    app.state.genai_client = client
    app.state.agenai_client = client.aio
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))


@app.on_event("shutdown")
async def shutdown() -> None:
    # 关闭 httpx 客户端
    http_client = getattr(app.state, "http_client", None)
    if http_client:
        await http_client.aclose()

    # genai 客户端
    aclient = getattr(app.state, "agenai_client", None)
    client = getattr(app.state, "genai_client", None)

    if aclient:
        for method_name in ("aclose", "close"):
            method = getattr(aclient, method_name, None)
            if callable(method):
                try:
                    result = method()
                    if hasattr(result, "__await__"):
                        await result
                    break
                except Exception:
                    pass

    if client:
        for method_name in ("close",):
            method = getattr(client, method_name, None)
            if callable(method):
                try:
                    method()
                    break
                except Exception:
                    pass


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


# =========================
# Retry Decorators
# =========================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _generate_images_with_retry(aclient, model: str, prompt: str, config):
    return await aclient.models.generate_images(
        model=model,
        prompt=prompt,
        config=config,
    )


# =========================
# Async Resource Loading
# =========================
async def _preload_raster_assets(
    doc: LayerDoc, http_client: httpx.AsyncClient
) -> Dict[str, bytes]:
    """预加载所有 RasterLayer 的 asset_url 资源"""
    urls_to_load: List[str] = []
    for layer in doc.layers:
        if isinstance(layer, RasterLayer) and layer.asset_url:
            urls_to_load.append(layer.asset_url)

    if not urls_to_load:
        return {}

    async def fetch_one(url: str) -> Tuple[str, Optional[bytes]]:
        try:
            r = await http_client.get(url, timeout=30.0)
            r.raise_for_status()
            return (url, r.content)
        except Exception:
            return (url, None)

    results = await asyncio.gather(*[fetch_one(u) for u in urls_to_load])
    return {url: data for url, data in results if data is not None}


# =========================
# 1) Vertex Imagen: Generate Base Image (No Text)
# =========================
@app.post("/v1/image/generate", tags=["Image Generation"])
async def image_generate(req: GenerateImageReq) -> JSONResponse:
    """
    生成"无字底图"，后续文字由 TextLayer 渲染，保证可编辑。
    """
    aclient = app.state.agenai_client

    prompt = (
        req.prompt
        + "\nImportant constraints: DO NOT render any text, letters, numbers, logos, watermarks in the image. "
        "Leave clean space areas for text boxes if needed."
    )

    try:
        resp = await _generate_images_with_retry(
            aclient,
            IMAGEN_MODEL,
            prompt,
            types.GenerateImagesConfig(
                number_of_images=req.number_of_images,
                output_mime_type=req.output_mime_type,
                include_rai_reason=True,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Imagen generate failed: {e}")

    images = []
    for gi in resp.generated_images or []:
        img_obj = gi.image
        if isinstance(img_obj, (bytes, bytearray)):
            img_bytes = bytes(img_obj)
        elif hasattr(img_obj, "save"):
            buf = io.BytesIO()
            fmt = "PNG" if req.output_mime_type == "image/png" else "JPEG"
            img_obj.save(buf, format=fmt)
            img_bytes = buf.getvalue()
        else:
            img_bytes = getattr(img_obj, "data", None)
            if not isinstance(img_bytes, (bytes, bytearray)):
                raise HTTPException(
                    status_code=500, detail="Unsupported image object returned by SDK"
                )

        images.append(
            {
                "mime_type": req.output_mime_type,
                "image_base64": _b64e(img_bytes),
                "rai_reason": getattr(gi, "rai_reason", None),
            }
        )

    return JSONResponse({"model": IMAGEN_MODEL, "images": images})


# =========================
# 2) Gemini: Suggest LayerDoc
# =========================
@app.post("/v1/layout/suggest", tags=["Layout"])
async def layout_suggest(
    req_json: str = Form(...),
    image: UploadFile = File(...),
) -> JSONResponse:
    """
    输入：一张底图/产品图 + 目标说明
    输出：LayerDoc JSON（文字框、形状层、渐变层建议）
    """
    aclient = app.state.agenai_client
    try:
        req = LayoutSuggestReq.model_validate_json(req_json)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid req_json: {e}")

    img_bytes = await image.read()
    mime = _guess_mime(image.filename)

    schema_hint = {
        "width": req.canvas_w,
        "height": req.canvas_h,
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
                "transform": {"x": 0, "y": 0, "scale": 1, "rotate": 0, "anchor_x": 0, "anchor_y": 0},
            },
            {
                "id": "badge_1",
                "type": "shape",
                "z": 10,
                "shape": "round_rect",
                "bbox": [120, 260, 820, 220],
                "style": {"fill": "#FFFFFFFF", "radius": 36},
                "transform": {"x": 0, "y": 0, "scale": 1, "rotate": 0, "anchor_x": 0, "anchor_y": 0},
            },
            {
                "id": "text_1",
                "type": "text",
                "z": 11,
                "text": "8小时续航",
                "bbox": [120, 260, 820, 220],
                "style": {"font_size": 88, "font_color": "#111827FF", "align": "center", "fit_to_box": True},
                "box_fill": None,
                "box_radius": 36,
                "box_padding": 34,
                "transform": {"x": 0, "y": 0, "scale": 1, "rotate": 0, "anchor_x": 0, "anchor_y": 0},
            },
        ],
    }

    prompt = f"""
你是资深电商附图设计师 + 前端分层渲染工程师。
目标：{req.goal}
要求：
- 输出严格 JSON，必须符合 LayerDoc 结构（不要 markdown，不要解释）。
- 画布：{req.canvas_w}x{req.canvas_h}。
- 底图必须无字；文字一定作为 TextLayer（可编辑），并放在矩形/圆角矩形容器框里。
- 最多 {req.max_text_boxes} 个文字框。
- 允许渐变背景（GradientLayer）、形状层（ShapeLayer）、文字层（TextLayer）。
- 文字内容要基于图片可见信息，不要编造看不出来的参数。
请参考此 JSON 结构样例（仅结构参考，内容需结合图片）：{json.dumps(schema_hint, ensure_ascii=False)}
"""

    contents = [
        prompt,
        types.Part.from_bytes(data=img_bytes, mime_type=mime),
    ]

    try:
        resp = await aclient.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config={"temperature": 0.25, "max_output_tokens": 4096},
        )
        text = getattr(resp, "text", "") or ""
        json_text = _extract_json_from_llm_response(text)

        try:
            layerdoc = json.loads(json_text)
        except json.JSONDecodeError as je:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse JSON: {je}. Raw: {text[:500]}",
            )

        validated = LayerDoc.model_validate(layerdoc)
        return JSONResponse(validated.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"layout suggest failed: {e}")


# =========================
# 3) Qwen-Image-Layered: Decompose into RGBA Layers
# =========================
@app.post("/v1/layers/decompose", tags=["Layer Decomposition"])
async def layers_decompose(image: UploadFile = File(...)) -> JSONResponse:
    """
    把扁平图拆为 RGBA 层（位图层），用于不规则图形分层编辑。
    需要设置 QWEN_LAYERED_ENDPOINT 环境变量。
    """
    if not QWEN_LAYERED_ENDPOINT:
        raise HTTPException(
            status_code=400,
            detail="QWEN_LAYERED_ENDPOINT is not set. You must provide a decompose service endpoint.",
        )

    img_bytes = await image.read()
    http_client: httpx.AsyncClient = app.state.http_client

    try:
        files = {
            "image": (image.filename or "image.png", img_bytes, _guess_mime(image.filename))
        }
        r = await http_client.post(
            QWEN_LAYERED_ENDPOINT,
            files=files,
            timeout=QWEN_LAYERED_TIMEOUT_SEC,
        )
        if r.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Qwen layered service error: {r.status_code} {r.text}",
            )
        data = r.json()
        layers = data.get("layers", [])
        if not isinstance(layers, list):
            raise HTTPException(status_code=502, detail="Invalid layered response schema.")
        return JSONResponse({"layers": layers})
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502, detail=f"Failed to call Qwen layered service: {e}"
        )


# =========================
# 4) NEW: Mask to SVG Vectorization
# =========================
@app.post("/v1/mask/vectorize", tags=["Vectorization"], response_model=VectorizeResponse)
async def mask_vectorize(
    image: UploadFile = File(..., description="Mask PNG (灰度或 RGBA，使用 alpha 通道)"),
    simplify_tolerance: float = Query(
        DEFAULT_SIMPLIFY_TOLERANCE,
        ge=0.1,
        le=20.0,
        description="RDP 简化容差（像素），值越大轮廓越简单"
    ),
    smooth_iterations: int = Query(
        DEFAULT_SMOOTH_ITERATIONS,
        ge=0,
        le=10,
        description="Chaikin 平滑迭代次数"
    ),
    use_bezier: bool = Query(
        True,
        description="是否输出贝塞尔曲线（更平滑）"
    ),
    bezier_smoothness: float = Query(
        0.25,
        ge=0.0,
        le=0.5,
        description="贝塞尔曲线平滑度"
    ),
    threshold: int = Query(
        128,
        ge=1,
        le=255,
        description="二值化阈值"
    ),
    blur_radius: float = Query(
        0.0,
        ge=0.0,
        le=10.0,
        description="预处理高斯模糊半径（减少噪点）"
    ),
) -> JSONResponse:
    """
    将 mask PNG 转换为可编辑的 SVG path。
    
    这是"真正像 PS 那样编辑轮廓"的关键功能。
    
    ## 用途
    
    1. 从 Qwen-Layered 分解得到的 RGBA 层中提取 alpha mask
    2. 将 mask 转换为 SVG path，前端可以像 PS 钢笔工具一样编辑锚点
    3. 编辑后的 SVG path 可以保存到 RasterLayer.mask_svg_path 或 ShapeLayer.svg_path_d
    4. 渲染时使用修改后的矢量路径
    
    ## 工作流程
    
    ```
    原图 → Qwen分层 → RGBA层 → mask/vectorize → SVG path → 前端编辑 → 保存到LayerDoc
    ```
    
    ## 返回
    
    - `svg`: 完整的 SVG 字符串
    - `svg_base64`: SVG 的 base64 编码（方便嵌入）
    - `paths`: 每个轮廓的 path 数据（id, d, points_count）
    - `width`, `height`: 原始尺寸
    - `contours_count`: 轮廓数量
    """
    img_bytes = await image.read()
    
    try:
        mask_img = Image.open(io.BytesIO(img_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
    
    try:
        result = vectorize_mask(
            mask_img,
            simplify_tolerance=simplify_tolerance,
            smooth_iterations=smooth_iterations,
            use_bezier=use_bezier,
            bezier_smoothness=bezier_smoothness,
            threshold=threshold,
            blur_radius=blur_radius,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vectorization failed: {e}")
    
    # 添加 base64 编码的 SVG
    svg_bytes = result["svg"].encode("utf-8")
    result["svg_base64"] = _b64e(svg_bytes)
    
    return JSONResponse(result)


@app.post("/v1/mask/vectorize/batch", tags=["Vectorization"])
async def mask_vectorize_batch(
    images: List[UploadFile] = File(..., description="多个 mask PNG 文件"),
    simplify_tolerance: float = Query(DEFAULT_SIMPLIFY_TOLERANCE, ge=0.1, le=20.0),
    smooth_iterations: int = Query(DEFAULT_SMOOTH_ITERATIONS, ge=0, le=10),
    use_bezier: bool = Query(True),
    bezier_smoothness: float = Query(0.25, ge=0.0, le=0.5),
    threshold: int = Query(128, ge=1, le=255),
    blur_radius: float = Query(0.0, ge=0.0, le=10.0),
) -> JSONResponse:
    """
    批量将多个 mask PNG 转换为 SVG path。
    
    适用于处理 Qwen-Layered 返回的多个图层。
    """
    results = []
    
    for i, image in enumerate(images):
        img_bytes = await image.read()
        
        try:
            mask_img = Image.open(io.BytesIO(img_bytes))
        except Exception as e:
            results.append({
                "index": i,
                "filename": image.filename,
                "error": f"Invalid image: {e}",
                "success": False,
            })
            continue
        
        try:
            result = vectorize_mask(
                mask_img,
                simplify_tolerance=simplify_tolerance,
                smooth_iterations=smooth_iterations,
                use_bezier=use_bezier,
                bezier_smoothness=bezier_smoothness,
                threshold=threshold,
                blur_radius=blur_radius,
            )
            svg_bytes = result["svg"].encode("utf-8")
            result["svg_base64"] = _b64e(svg_bytes)
            result["index"] = i
            result["filename"] = image.filename
            result["success"] = True
            results.append(result)
        except Exception as e:
            results.append({
                "index": i,
                "filename": image.filename,
                "error": f"Vectorization failed: {e}",
                "success": False,
            })
    
    return JSONResponse({
        "total": len(images),
        "success_count": sum(1 for r in results if r.get("success", False)),
        "results": results,
    })


# =========================
# 5) Text Rendering
# =========================
def _render_text_in_box(
    draw: ImageDraw.ImageDraw,
    bbox: Tuple[int, int, int, int],
    text: str,
    style: TextStyle,
) -> None:
    """在指定 bbox 内渲染文字"""
    x, y, w, h = bbox

    def wrap_lines(font: ImageFont.ImageFont, s: str, max_w: int) -> List[str]:
        """按字符宽度换行"""
        lines: List[str] = []
        cur = ""
        for ch in s:
            nxt = cur + ch
            if draw.textlength(nxt, font=font) <= max_w:
                cur = nxt
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines if lines else [""]

    available_w = max(10, w)
    available_h = max(10, h)

    font_size = style.font_size
    if style.fit_to_box:
        for size in range(style.font_size, 10, -2):
            font = _load_font(size)
            lines = wrap_lines(font, text, available_w)
            line_h = int(size * style.line_spacing)
            total_h = line_h * len(lines)
            if total_h <= available_h and all(
                draw.textlength(line, font=font) <= available_w for line in lines
            ):
                font_size = size
                break

    font = _load_font(font_size)
    lines = wrap_lines(font, text, available_w)
    line_h = int(font_size * style.line_spacing)
    total_h = line_h * len(lines)
    start_y = y + (available_h - total_h) // 2

    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font)

        if style.align == "left":
            tx = x
        elif style.align == "right":
            tx = x + w - int(tw)
        else:  # center
            tx = x + (w - int(tw)) // 2

        ty = start_y + i * line_h

        # 阴影
        if style.shadow_color:
            sc = _rgba_tuple(style.shadow_color)
            draw.text(
                (tx + style.shadow_dx, ty + style.shadow_dy), line, font=font, fill=sc
            )

        # 文字（带可选描边）
        fill = _rgba_tuple(style.font_color)
        if style.stroke_color and style.stroke_width > 0:
            stroke_fill = _rgba_tuple(style.stroke_color)
            draw.text(
                (tx, ty),
                line,
                font=font,
                fill=fill,
                stroke_width=style.stroke_width,
                stroke_fill=stroke_fill,
            )
        else:
            draw.text((tx, ty), line, font=font, fill=fill)


# =========================
# 6) SVG Path Rendering (for ShapeLayer with shape="path")
# =========================
def _render_svg_path_to_mask(
    path_d: str, width: int, height: int
) -> Optional[Image.Image]:
    """
    将 SVG path d 属性渲染为 PIL mask 图像。
    
    简化实现：解析 M, L, C, Z 命令绘制到 PIL。
    生产环境建议使用 cairosvg 或 svglib。
    """
    if not path_d:
        return None
    
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    
    # 简化解析：提取所有点坐标
    # 支持 M, L, C, Q, Z 命令
    commands = re.findall(r'([MLCQZ])\s*([-\d.,\s]*)', path_d.upper())
    
    points = []
    current_x, current_y = 0.0, 0.0
    
    for cmd, args in commands:
        nums = [float(n) for n in re.findall(r'-?\d+\.?\d*', args)]
        
        if cmd == 'M' and len(nums) >= 2:
            current_x, current_y = nums[0], nums[1]
            points.append((current_x, current_y))
        elif cmd == 'L' and len(nums) >= 2:
            current_x, current_y = nums[0], nums[1]
            points.append((current_x, current_y))
        elif cmd == 'C' and len(nums) >= 6:
            # 三次贝塞尔：取终点
            current_x, current_y = nums[4], nums[5]
            points.append((current_x, current_y))
        elif cmd == 'Q' and len(nums) >= 4:
            # 二次贝塞尔：取终点
            current_x, current_y = nums[2], nums[3]
            points.append((current_x, current_y))
        elif cmd == 'Z':
            pass  # 闭合
    
    if len(points) >= 3:
        # 转换为整数坐标
        polygon = [(int(x), int(y)) for x, y in points]
        draw.polygon(polygon, fill=255)
    
    return mask


# =========================
# 7) LayerDoc Rendering
# =========================
def _render_layerdoc_to_image(
    doc: LayerDoc, preloaded_assets: Optional[Dict[str, bytes]] = None
) -> Image.Image:
    """渲染 LayerDoc 到 PIL Image"""
    preloaded_assets = preloaded_assets or {}

    canvas = Image.new("RGBA", (doc.width, doc.height), (255, 255, 255, 0))
    if doc.background:
        canvas = Image.new("RGBA", (doc.width, doc.height), _rgba_tuple(doc.background))

    layers_sorted = sorted(doc.layers, key=lambda l: l.z)

    for layer in layers_sorted:
        opacity = _clamp01(layer.opacity)

        # GradientLayer
        if isinstance(layer, GradientLayer):
            stops = [(float(t), _rgba_tuple(c)) for t, c in layer.stops]
            grad = _linear_gradient_rgba(doc.width, doc.height, layer.angle, stops)
            grad = _apply_opacity_rgba(grad, opacity)
            _paste_with_alpha(canvas, grad, (0, 0))
            continue

        # ShapeLayer
        if isinstance(layer, ShapeLayer):
            x, y, w, h = layer.bbox
            shp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(shp)

            # 填充：纯色或渐变
            fill_img: Optional[Image.Image] = None
            if layer.style.gradient:
                angle = float(layer.style.gradient.get("angle", 0.0))
                stops_raw = layer.style.gradient.get("stops", [])
                stops = [(float(t), _rgba_tuple(c)) for t, c in stops_raw]
                fill_img = _linear_gradient_rgba(w, h, angle, stops)
            else:
                if layer.style.fill:
                    fill_img = Image.new("RGBA", (w, h), _rgba_tuple(layer.style.fill))

            # 画形状 mask
            mask = Image.new("L", (w, h), 0)
            md = ImageDraw.Draw(mask)
            
            if layer.shape == "path" and layer.svg_path_d:
                # 使用 SVG path
                path_mask = _render_svg_path_to_mask(layer.svg_path_d, w, h)
                if path_mask:
                    mask = path_mask
            elif layer.shape == "round_rect":
                r = max(0, int(layer.style.radius))
                md.rounded_rectangle([0, 0, w, h], radius=r, fill=255)
            elif layer.shape == "ellipse":
                md.ellipse([0, 0, w, h], fill=255)
            else:  # rect
                md.rectangle([0, 0, w, h], fill=255)

            # 贴 fill
            if fill_img is not None:
                shp.alpha_composite(fill_img)
                # 用 mask 限制形状
                arr = np.array(shp)
                a = np.array(mask).astype(np.float32)
                arr[..., 3] = (arr[..., 3].astype(np.float32) * (a / 255.0)).astype(np.uint8)
                shp = Image.fromarray(arr, mode="RGBA")

            # stroke
            if layer.style.stroke and layer.style.stroke_width > 0:
                sw = int(layer.style.stroke_width)
                stroke = _rgba_tuple(layer.style.stroke)
                if layer.shape == "round_rect":
                    r = max(0, int(layer.style.radius))
                    d.rounded_rectangle(
                        [sw // 2, sw // 2, w - sw // 2, h - sw // 2],
                        radius=r,
                        outline=stroke,
                        width=sw,
                    )
                elif layer.shape == "ellipse":
                    d.ellipse(
                        [sw // 2, sw // 2, w - sw // 2, h - sw // 2],
                        outline=stroke,
                        width=sw,
                    )
                else:
                    d.rectangle(
                        [sw // 2, sw // 2, w - sw // 2, h - sw // 2],
                        outline=stroke,
                        width=sw,
                    )

            shp = _apply_opacity_rgba(shp, opacity)
            _paste_with_alpha(canvas, shp, (x, y))
            continue

        # TextLayer
        if isinstance(layer, TextLayer):
            x, y, w, h = layer.bbox
            box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            bd = ImageDraw.Draw(box)

            if layer.box_fill:
                fill = _rgba_tuple(layer.box_fill)
                r = max(0, int(layer.box_radius))
                bd.rounded_rectangle([0, 0, w, h], radius=r, fill=fill)

            txt_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            td = ImageDraw.Draw(txt_img)

            pad = int(layer.box_padding)
            inner_bbox = (pad, pad, w - 2 * pad, h - 2 * pad)
            _render_text_in_box(td, inner_bbox, layer.text, layer.style)

            box.alpha_composite(txt_img)
            box = _apply_opacity_rgba(box, opacity)
            _paste_with_alpha(canvas, box, (x, y))
            continue

        # RasterLayer
        if isinstance(layer, RasterLayer):
            # 获取位图
            if layer.png_base64:
                img = Image.open(io.BytesIO(_b64d(layer.png_base64))).convert("RGBA")
            elif layer.asset_url:
                asset_bytes = preloaded_assets.get(layer.asset_url)
                if asset_bytes is None:
                    continue
                img = Image.open(io.BytesIO(asset_bytes)).convert("RGBA")
            else:
                continue

            # mask 处理：优先使用 SVG path，其次 PNG mask
            mask_applied = False
            
            if layer.mask_svg_path:
                # 使用 SVG path 作为 mask
                svg_mask = _render_svg_path_to_mask(
                    layer.mask_svg_path, img.width, img.height
                )
                if svg_mask:
                    arr = np.array(img)
                    m = np.array(svg_mask).astype(np.float32) / 255.0
                    arr[..., 3] = (arr[..., 3].astype(np.float32) * m).astype(np.uint8)
                    img = Image.fromarray(arr, mode="RGBA")
                    mask_applied = True
            
            if not mask_applied and layer.mask_png_base64:
                # 使用 PNG mask
                mask = Image.open(io.BytesIO(_b64d(layer.mask_png_base64))).convert("L")
                arr = np.array(img)
                m = np.array(mask).astype(np.float32) / 255.0
                arr[..., 3] = (arr[..., 3].astype(np.float32) * m).astype(np.uint8)
                img = Image.fromarray(arr, mode="RGBA")

            # transform
            tx, ty = int(layer.transform.x), int(layer.transform.y)
            if abs(layer.transform.scale - 1.0) > 1e-3:
                nw = max(1, int(img.width * layer.transform.scale))
                nh = max(1, int(img.height * layer.transform.scale))
                img = img.resize((nw, nh), resample=Image.BICUBIC)

            img = _apply_opacity_rgba(img, opacity)
            _paste_with_alpha(canvas, img, (tx, ty))
            continue

    return canvas


# =========================
# 8) Render/Compose Endpoint
# =========================
@app.post("/v1/render/compose", tags=["Rendering"])
async def render_compose(doc_json: str = Form(...)) -> Response:
    """
    输入 LayerDoc JSON，输出 PNG（二进制）。
    
    前端改文字/改布局/改 SVG path 后直接再次调用此接口即可得到新图。
    """
    try:
        doc_raw = json.loads(doc_json)
        doc = LayerDoc.model_validate(doc_raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid LayerDoc: {e}")

    try:
        http_client: httpx.AsyncClient = app.state.http_client
        preloaded = await _preload_raster_assets(doc, http_client)
        img = _render_layerdoc_to_image(doc, preloaded_assets=preloaded)
        png = _pil_to_png_bytes(img)
        return Response(content=png, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render failed: {e}")


@app.post("/v1/render/compose/base64", tags=["Rendering"])
async def render_compose_base64(doc_json: str = Form(...)) -> JSONResponse:
    """
    输入 LayerDoc JSON，输出 PNG 的 base64 编码。
    
    方便前端直接使用 data URL。
    """
    try:
        doc_raw = json.loads(doc_json)
        doc = LayerDoc.model_validate(doc_raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid LayerDoc: {e}")

    try:
        http_client: httpx.AsyncClient = app.state.http_client
        preloaded = await _preload_raster_assets(doc, http_client)
        img = _render_layerdoc_to_image(doc, preloaded_assets=preloaded)
        png = _pil_to_png_bytes(img)
        return JSONResponse({
            "image_base64": _b64e(png),
            "mime_type": "image/png",
            "width": doc.width,
            "height": doc.height,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render failed: {e}")


# =========================
# Local run:
#   uvicorn main:app --reload --host 0.0.0.0 --port 8000
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
