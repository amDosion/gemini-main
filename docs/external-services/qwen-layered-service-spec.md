# Qwen-Image-Layered 外部服务开发规范

## 1. 概述

本文档定义了 **Qwen-Image-Layered 图层分解服务** 的接口规范，供独立部署的 GPU 服务开发参考。

### 1.1 服务定位

| 属性 | 说明 |
|------|------|
| 功能 | 将图片分解为多个 RGBA 透明图层 |
| 模型 | Qwen/Qwen-Image-Layered (ModelScope) |
| 部署 | 独立 GPU 服务器，资源隔离 |
| 通信 | HTTP REST API |
| 认证 | Bearer Token（独立于主系统） |

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     主系统 (Backend)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  LayeredDesignService.decompose_layers()            │   │
│  │     │                                               │   │
│  │     ▼                                               │   │
│  │  HTTP POST with Authorization: Bearer <API_KEY>     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Qwen-Layered 外部服务 (GPU Server)              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  POST /decompose                                    │   │
│  │     │                                               │   │
│  │     ▼                                               │   │
│  │  1. 验证 Authorization header                       │   │
│  │  2. 解析图片和参数                                   │   │
│  │  3. 调用 QwenImageLayeredPipeline                   │   │
│  │  4. 返回分层结果                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 环境配置

### 2.1 主系统配置 (.env)

在主系统的 `backend/.env` 中配置：

```bash
# =============================================================================
# Qwen-Image-Layered 图层分解服务
# =============================================================================

# 服务端点（必填）
# 格式: http://域名或IP:端口/路径
QWEN_LAYERED_ENDPOINT=http://192.168.50.200:7860/decompose

# 认证密钥（可选，推荐配置）
# 此密钥由外部服务管理，与主系统 JWT 完全独立
QWEN_LAYERED_API_KEY=your-external-service-api-key-here

# 请求超时（秒，默认 180）
# 图层分解需要较长时间，建议 180-300 秒
QWEN_LAYERED_TIMEOUT_SEC=180
```

### 2.2 外部服务环境变量

外部服务建议支持以下环境变量：

```bash
# 服务端口
PORT=7860

# 认证密钥（用于验证请求）
API_KEY=your-external-service-api-key-here

# 模型配置
MODEL_DIR=/models/Qwen-Image-Layered
DEVICE=cuda
DTYPE=bfloat16

# 性能配置
MAX_WORKERS=2
DEFAULT_RESOLUTION=640
DEFAULT_LAYERS=4
```

---

## 3. API 接口规范

### 3.1 图层分解接口

**端点**: `POST /decompose`

**Content-Type**: `multipart/form-data`

#### 请求头

| Header | 必填 | 说明 |
|--------|------|------|
| `Authorization` | 可选 | `Bearer <API_KEY>` 格式 |
| `Content-Type` | 是 | `multipart/form-data` |

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image` | File | 是 | - | 输入图片文件 (PNG/JPEG) |
| `layers` | String | 否 | "4" | 分解图层数 (2-10) |
| `seed` | String | 否 | "-1" | 随机种子，-1 表示随机 |
| `prompt` | String | 否 | "" | 图片描述（可选） |

#### 请求示例 (cURL)

```bash
curl -X POST "http://192.168.50.200:7860/decompose" \
  -H "Authorization: Bearer your-api-key" \
  -F "image=@input.png" \
  -F "layers=4" \
  -F "seed=-1" \
  -F "prompt=A product photo with white background"
```

#### 请求示例 (Python)

```python
import httpx

async def decompose_image(image_bytes: bytes, layers: int = 4, seed: int = -1):
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            "http://192.168.50.200:7860/decompose",
            headers={"Authorization": "Bearer your-api-key"},
            files={"image": ("image.png", image_bytes, "image/png")},
            data={"layers": str(layers), "seed": str(seed)}
        )
        return response.json()
```

### 3.2 响应格式

#### 成功响应 (200 OK)

```json
{
  "success": true,
  "layers": [
    {
      "id": "layer_0",
      "name": "Background",
      "z": 0,
      "png_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
      "width": 640,
      "height": 640
    },
    {
      "id": "layer_1",
      "name": "Layer 1",
      "z": 1,
      "png_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
      "width": 640,
      "height": 640
    },
    {
      "id": "layer_2",
      "name": "Layer 2",
      "z": 2,
      "png_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
      "width": 640,
      "height": 640
    },
    {
      "id": "layer_3",
      "name": "Layer 3",
      "z": 3,
      "png_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
      "width": 640,
      "height": 640
    }
  ],
  "total": 4,
  "seed": 12345,
  "width": 640,
  "height": 640,
  "processing_time_ms": 15234
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `layers` | array | 图层数组，按 z 顺序排列 |
| `layers[].id` | string | 图层唯一标识，格式 `layer_{index}` |
| `layers[].name` | string | 图层名称，`Background` 或 `Layer {n}` |
| `layers[].z` | number | 图层顺序，0 为最底层 |
| `layers[].png_base64` | string | Base64 编码的 PNG 图片（含透明通道） |
| `layers[].width` | number | 图层宽度（像素） |
| `layers[].height` | number | 图层高度（像素） |
| `total` | number | 图层总数 |
| `seed` | number | 实际使用的随机种子 |
| `width` | number | 输出图片宽度 |
| `height` | number | 输出图片高度 |
| `processing_time_ms` | number | 处理耗时（毫秒，可选） |

#### 错误响应

**认证失败 (401)**

```json
{
  "success": false,
  "error": "Invalid or missing API key",
  "code": "AUTH_FAILED"
}
```

**参数错误 (400)**

```json
{
  "success": false,
  "error": "Invalid layers parameter: must be between 2 and 10",
  "code": "INVALID_PARAMS"
}
```

**服务器错误 (500)**

```json
{
  "success": false,
  "error": "Model inference failed: CUDA out of memory",
  "code": "INFERENCE_ERROR"
}
```

### 3.3 健康检查接口（可选）

**端点**: `GET /health`

**响应**:

```json
{
  "status": "healthy",
  "model_loaded": true,
  "gpu_available": true,
  "gpu_memory_used_mb": 8192,
  "gpu_memory_total_mb": 16384
}
```

---

## 4. 认证机制

### 4.1 Bearer Token 认证

服务应支持 `Authorization: Bearer <token>` 格式的认证：

```python
from fastapi import FastAPI, Header, HTTPException

API_KEY = os.getenv("API_KEY", "")

def verify_auth(authorization: str = Header(None)):
    """验证 Authorization header"""
    if not API_KEY:
        # 未配置密钥时跳过验证
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization format")

    token = authorization[7:]  # 去掉 "Bearer " 前缀

    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True
```

### 4.2 无认证模式

如果 `API_KEY` 环境变量未设置，服务可以选择：
- 跳过认证（开发/测试环境）
- 拒绝所有请求（生产环境推荐）

---

## 5. 参考实现

### 5.1 基于 FastAPI 的实现

```python
"""
Qwen-Image-Layered 图层分解服务

启动命令:
    uvicorn main:app --host 0.0.0.0 --port 7860

环境变量:
    API_KEY: 认证密钥
    MODEL_DIR: 模型目录
"""

import os
import io
import base64
import random
import time
from typing import Optional

import numpy as np
import torch
from PIL import Image
from fastapi import FastAPI, File, Form, UploadFile, Header, HTTPException
from fastapi.responses import JSONResponse
from diffusers import QwenImageLayeredPipeline
from modelscope import snapshot_download

# 配置
API_KEY = os.getenv("API_KEY", "")
MODEL_DIR = os.getenv("MODEL_DIR", "")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16
MAX_SEED = np.iinfo(np.int32).max

# 初始化模型
if not MODEL_DIR:
    MODEL_DIR = snapshot_download("Qwen/Qwen-Image-Layered")

pipeline = QwenImageLayeredPipeline.from_pretrained(
    MODEL_DIR,
    torch_dtype=DTYPE
).to(DEVICE)

app = FastAPI(title="Qwen-Image-Layered Service")


def verify_auth(authorization: Optional[str]) -> bool:
    """验证认证"""
    if not API_KEY:
        return True

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if authorization[7:] != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return True


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": pipeline is not None,
        "gpu_available": torch.cuda.is_available(),
        "device": DEVICE
    }


@app.post("/decompose")
async def decompose(
    image: UploadFile = File(...),
    layers: str = Form("4"),
    seed: str = Form("-1"),
    prompt: str = Form(""),
    authorization: Optional[str] = Header(None)
):
    """图层分解接口"""
    # 认证
    verify_auth(authorization)

    start_time = time.time()

    try:
        # 参数解析
        num_layers = int(layers)
        if num_layers < 2 or num_layers > 10:
            raise HTTPException(
                status_code=400,
                detail="layers must be between 2 and 10"
            )

        seed_value = int(seed)
        if seed_value == -1:
            seed_value = random.randint(0, MAX_SEED)

        # 读取图片
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

        # 模型推理
        inputs = {
            "image": pil_image,
            "generator": torch.Generator(device=DEVICE).manual_seed(seed_value),
            "layers": num_layers,
            "resolution": 640,
            "prompt": prompt if prompt else None,
            "num_inference_steps": 50,
            "true_cfg_scale": 4.0,
        }

        with torch.inference_mode():
            output = pipeline(**inputs)
            output_images = output.images[0]

        # 构建响应
        result_layers = []
        for i, img in enumerate(output_images):
            # 转换为 Base64
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            result_layers.append({
                "id": f"layer_{i}",
                "name": "Background" if i == 0 else f"Layer {i}",
                "z": i,
                "png_base64": png_base64,
                "width": img.width,
                "height": img.height
            })

        processing_time = int((time.time() - start_time) * 1000)

        return JSONResponse({
            "success": True,
            "layers": result_layers,
            "total": len(result_layers),
            "seed": seed_value,
            "width": result_layers[0]["width"] if result_layers else 0,
            "height": result_layers[0]["height"] if result_layers else 0,
            "processing_time_ms": processing_time
        })

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "code": "INFERENCE_ERROR"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
```

### 5.2 Dockerfile

```dockerfile
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    python-multipart \
    diffusers \
    modelscope \
    pillow \
    numpy

# 复制代码
COPY main.py .

# 预下载模型（可选，或挂载模型目录）
# RUN python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen-Image-Layered')"

# 环境变量
ENV PORT=7860
ENV API_KEY=""
ENV MODEL_DIR=""

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```

### 5.3 Docker Compose

```yaml
version: '3.8'

services:
  qwen-layered:
    build: .
    ports:
      - "7860:7860"
    environment:
      - API_KEY=${QWEN_LAYERED_API_KEY}
      - MODEL_DIR=/models/Qwen-Image-Layered
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
```

---

## 6. 部署建议

### 6.1 硬件要求

| 资源 | 最低配置 | 推荐配置 |
|------|----------|----------|
| GPU | NVIDIA RTX 3080 (10GB) | NVIDIA RTX 4090 (24GB) |
| VRAM | 12GB | 16GB+ |
| RAM | 16GB | 32GB |
| 存储 | 50GB SSD | 100GB NVMe |

### 6.2 性能优化

1. **模型预加载**: 启动时加载模型到 GPU，避免首次请求延迟
2. **请求队列**: 使用 Celery/RQ 管理并发请求
3. **批处理**: 支持多图批量处理（可选）
4. **缓存**: 相同 seed 的结果可缓存

### 6.3 监控指标

建议监控以下指标：

- GPU 利用率和显存使用
- 请求延迟 (P50, P95, P99)
- 请求成功率
- 队列长度（如使用队列）

---

## 7. 错误码参考

| 错误码 | HTTP 状态 | 说明 |
|--------|----------|------|
| `AUTH_FAILED` | 401 | 认证失败 |
| `ACCESS_DENIED` | 403 | 访问被拒绝 |
| `INVALID_PARAMS` | 400 | 参数无效 |
| `INVALID_IMAGE` | 400 | 图片格式无效 |
| `INFERENCE_ERROR` | 500 | 模型推理失败 |
| `OUT_OF_MEMORY` | 500 | GPU 显存不足 |
| `TIMEOUT` | 504 | 处理超时 |

---

## 8. 测试用例

### 8.1 基本功能测试

```python
import httpx
import base64

async def test_decompose():
    # 读取测试图片
    with open("test_image.png", "rb") as f:
        image_bytes = f.read()

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            "http://localhost:7860/decompose",
            headers={"Authorization": "Bearer test-api-key"},
            files={"image": ("test.png", image_bytes, "image/png")},
            data={"layers": "4", "seed": "12345"}
        )

    result = response.json()

    assert result["success"] == True
    assert len(result["layers"]) == 4
    assert result["seed"] == 12345

    # 验证图层可以解码
    for layer in result["layers"]:
        png_bytes = base64.b64decode(layer["png_base64"])
        assert len(png_bytes) > 0

# 运行测试
import asyncio
asyncio.run(test_decompose())
```

### 8.2 认证测试

```python
async def test_auth_required():
    async with httpx.AsyncClient() as client:
        # 无认证
        response = await client.post(
            "http://localhost:7860/decompose",
            files={"image": ("test.png", b"fake", "image/png")}
        )
        assert response.status_code == 401

        # 错误密钥
        response = await client.post(
            "http://localhost:7860/decompose",
            headers={"Authorization": "Bearer wrong-key"},
            files={"image": ("test.png", b"fake", "image/png")}
        )
        assert response.status_code == 401
```

---

## 9. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-01-30 | 初始版本 |

---

## 10. 联系方式

如有问题，请联系项目维护团队。
