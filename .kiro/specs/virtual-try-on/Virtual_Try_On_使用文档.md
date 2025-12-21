# Virtual Try-On 虚拟试衣应用使用文档

## 概述

Virtual Try-On 是一个基于 Gemini 2.5 和 Imagen 3 的虚拟试衣应用，能够通过 AI 技术实现在图像中虚拟替换服装的功能。该应用利用 Gemini 2.5 的图像理解能力进行精确的服装分割，结合 Imagen 3 的图像编辑能力实现逼真的服装替换效果。

### 核心特性

- **智能分割**：使用 Gemini 2.5 进行参考表达式分割（Referring Expression Segmentation），无需额外的分割模型
- **高质量编辑**：基于 Imagen 3 进行图像修复和编辑，生成逼真的替换效果
- **灵活配置**：支持多种编辑模式和参数调整，满足不同场景需求
- **易于使用**：在 Google Colab 环境中即可运行，无需复杂的本地环境配置

---

## 技术架构

### 核心技术组件

#### 1. Gemini 2.5（图像分割）
- **功能**：理解图像内容并生成精确的分割掩码
- **支持模型**：
  - `gemini-2.5-flash-lite`：轻量级，速度快
  - `gemini-2.5-flash`：平衡性能和质量
  - `gemini-2.5-pro`：最高质量
  - `gemini-3-flash-preview`：最新预览版本（默认）
  - `gemini-3-pro-preview`：最高性能预览版

- **输入**：
  - 图像文件
  - 文本描述（要分割的物体，如 "hoodie", "jacket" 等）

- **输出**：
  - JSON 格式的分割数据，包含：
    - `box_2d`：归一化的边界框坐标（基于 1000 的坐标系统）
    - `mask`：base64 编码的 PNG 掩码图像
    - `label`：物体标签

#### 2. Imagen 3（图像编辑）
- **模型**：`imagen-3.0-capability-001`
- **功能**：基于掩码进行精确的图像编辑和修复
- **编辑模式**：
  - `inpainting-insert`：在掩码区域插入新内容（用于替换服装）
  - `inpainting-remove`：移除掩码区域的内容
  - `outpainting`：扩展图像边界

- **掩码模式**：
  - `foreground`：编辑前景（掩码区域）
  - `background`：编辑背景（非掩码区域）

#### 3. 支持库
- **google-genai**：Gemini API SDK
- **vertexai**：Vertex AI Python SDK（用于 Imagen 3）
- **cv2（OpenCV）**：图像处理和掩码操作
- **numpy**：数值计算和数组操作
- **PIL（Pillow）**：图像加载和保存
- **matplotlib**：结果可视化

### 工作流程

```
1. 输入原始图像
   ↓
2. Gemini 2.5 分析图像并生成分割掩码
   ↓
3. 处理和调整掩码
   ↓
4. 配置编辑参数（提示词、编辑模式等）
   ↓
5. Imagen 3 基于掩码和提示词生成编辑后的图像
   ↓
6. 输出结果图像
```

---

## 环境要求

### 前置条件

#### 重要：两种不同的认证方式

本应用使用**两套独立的 API 系统**，需要不同的认证方式：

| API 系统 | 用途 | 认证方式 | 需要什么 |
|---------|------|---------|---------|
| **Gemini API** | 图像分割（Gemini 2.5） | API Key | `GOOGLE_API_KEY` |
| **Vertex AI** | 图像编辑和超分辨率（Imagen 3/4） | GCP 项目认证 | `GCP_PROJECT_ID` + OAuth 认证 |

#### 1. Gemini API 访问权限（用于图像分割）
- **需要**：Gemini API 密钥（API Key）
- **获取方式**：访问 [Google AI Studio](https://aistudio.google.com/)
- **格式示例**：`AIzaSyA...`（长字符串）
- **用途**：调用 Gemini 2.5 进行服装分割

#### 2. GCP 账户和 Vertex AI（用于图像编辑）
- **需要**：
  - ✅ Google Cloud Platform 账户
  - ✅ GCP 项目 ID（**不是** API Key）
  - ✅ 已启用 Vertex AI API
  - ✅ 已配置计费账户
  - ✅ OAuth 认证（通过 `auth.authenticate_user()`）
- **不需要**：❌ Vertex AI 的单独 API Key
- **格式示例**：项目 ID 如 `my-project-123456`
- **设置指南**：[Vertex AI 环境设置](https://cloud.google.com/vertex-ai/docs/start/cloud-environment)
- **用途**：调用 Imagen 3 进行图像编辑和 Imagen 4 进行超分辨率

#### 3. 运行环境

**本文档中的所有功能都是通过 API 调用实现**，可以在以下环境中运行：

- ✅ **本地 Python 环境**（推荐用于生产）
- ✅ **本地 Jupyter Notebook**
- ✅ **Google Colab**（适合快速测试）
- ✅ **任何支持 Python 的云环境**

> 💡 **重要**：无论使用哪种环境，所有功能都是通过调用 Google API 实现，**不需要使用网页控制台**。

### 依赖安装

#### 在本地环境中

```bash
# 安装必需的 SDK
pip install -U google-genai
pip install -U google-cloud-aiplatform

# 安装图像处理库
pip install opencv-python numpy pillow matplotlib
```

#### 在 Google Colab 中

```python
# Colab 已预装大部分库，只需安装 Gemini SDK
%pip install -U -q google-genai
```

### 环境配置

根据运行环境不同，配置方式有所区别：

---

#### 选项 1：本地环境配置（推荐用于生产）

##### 步骤 1：安装依赖

```bash
pip install -U google-genai google-cloud-aiplatform
pip install opencv-python numpy pillow matplotlib
```

##### 步骤 2：配置认证

**方法 A：使用环境变量（推荐）**

```bash
# Linux/macOS
export GOOGLE_API_KEY="你的Gemini_API密钥"
export GCP_PROJECT_ID="你的GCP项目ID"

# Windows PowerShell
$env:GOOGLE_API_KEY="你的Gemini_API密钥"
$env:GCP_PROJECT_ID="你的GCP项目ID"

# Windows CMD
set GOOGLE_API_KEY=你的Gemini_API密钥
set GCP_PROJECT_ID=你的GCP项目ID
```

**方法 B：使用配置文件**

创建 `.env` 文件：
```
GOOGLE_API_KEY=AIzaSyA...
GCP_PROJECT_ID=my-project-123456
```

在代码中加载：
```python
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
```

##### 步骤 3：GCP 认证（用于 Vertex AI）

**方法 A：使用服务账号（生产环境推荐）**

```bash
# 1. 在 GCP Console 创建服务账号
# 2. 下载 JSON 密钥文件
# 3. 设置环境变量
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

**方法 B：使用 gcloud CLI 认证（开发环境推荐）**

```bash
# 安装 gcloud CLI
# 访问：https://cloud.google.com/sdk/docs/install

# 登录你的 Google 账户
gcloud auth login

# 设置默认项目
gcloud config set project 你的项目ID

# 为应用设置默认凭证
gcloud auth application-default login
```

##### 步骤 4：使用代码

```python
import os
from google import genai
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel, Image

# ═══════════════════════════════════════════════════════════
# 1. 配置 Gemini API（图像分割）
# ═══════════════════════════════════════════════════════════
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)

# ═══════════════════════════════════════════════════════════
# 2. 配置 Vertex AI（图像编辑）
# ═══════════════════════════════════════════════════════════
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')

# 初始化 Vertex AI（自动使用环境凭证）
vertexai.init(
    project=GCP_PROJECT_ID,
    location="us-central1"
)

# 现在可以使用所有功能
print("✅ 认证配置完成，可以开始使用 API")
```

---

#### 选项 2：Google Colab 配置（适合快速测试）

##### 配置 Colab Secrets

在 Google Colab 中，需要配置以下两个 Secrets：

| Secret 名称 | 用途 | 获取方式 | 格式示例 |
|------------|------|---------|----------|
| `GOOGLE_API_KEY` | Gemini API 密钥 | [Google AI Studio](https://aistudio.google.com/) | `AIzaSyA...` |
| `GCP_PROJECT_ID` | GCP 项目 ID | [GCP Console](https://console.cloud.google.com/) | `my-project-123456` |

**配置步骤**：
1. 在 Colab 中点击左侧边栏的 🔑 图标
2. 点击"Add new secret"
3. 添加 `GOOGLE_API_KEY`：
   - Name: `GOOGLE_API_KEY`
   - Value: 你的 Gemini API 密钥（从 AI Studio 获取）
4. 添加 `GCP_PROJECT_ID`：
   - Name: `GCP_PROJECT_ID`
   - Value: 你的 GCP 项目 ID（**不是**项目名称）

#### 如何获取 GCP 项目 ID

⚠️ **注意**：项目 ID ≠ 项目名称

**方法 1：通过 GCP Console**
1. 访问 https://console.cloud.google.com/
2. 点击顶部的项目选择器
3. 在弹出窗口中，复制**"ID"**列的值（不是"名称"列）

**示例**：
```
项目名称：My Cool Project       ← 不是这个
项目 ID：my-cool-project-123456  ← 使用这个
项目编号：987654321012           ← 也不是这个
```

**方法 2：使用 gcloud 命令**
```bash
gcloud config get-value project
```

##### Colab 中的认证流程

```python
from google.colab import userdata, auth

# ═══════════════════════════════════════════════════════════
# 步骤 1：OAuth 认证（登录 Google 账户）
# ═══════════════════════════════════════════════════════════
# 这会弹出一个登录窗口，选择你的 GCP 账户并授权
auth.authenticate_user()

# ═══════════════════════════════════════════════════════════
# 步骤 2：配置 Gemini API（用于图像分割）
# ═══════════════════════════════════════════════════════════
# 使用 API Key 认证
GEMINI_API_KEY = userdata.get('GOOGLE_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)

# ═══════════════════════════════════════════════════════════
# 步骤 3：配置 Vertex AI（用于图像编辑）
# ═══════════════════════════════════════════════════════════
# 使用项目 ID + OAuth 认证（不需要 API Key）
GCP_PROJECT_ID = userdata.get('GCP_PROJECT_ID')
vertexai.init(project=GCP_PROJECT_ID, location="us-central1")

print("✅ Colab 认证配置完成")
```

---

### 环境对比总结

| 特性 | 本地环境 | Google Colab |
|------|---------|-------------|
| **API 调用方式** | ✅ 完全相同 | ✅ 完全相同 |
| **Gemini 认证** | 环境变量/配置文件 | Colab Secrets |
| **Vertex AI 认证** | gcloud CLI / 服务账号 | OAuth 弹窗 |
| **适用场景** | 生产部署、长期项目 | 快速测试、演示 |
| **优势** | 更灵活、更安全 | 配置简单、即开即用 |

---

### 常见认证错误

❌ **错误 1：混淆项目名称和项目 ID**
```python
# 错误
vertexai.init(project="My Cool Project", ...)

# 正确
vertexai.init(project="my-cool-project-123456", ...)
```

❌ **错误 2：以为 Vertex AI 需要 API Key**
```python
# 错误：Vertex AI 没有这个参数
vertexai.init(api_key="some_key", ...)

# 正确：使用项目 ID
vertexai.init(project=GCP_PROJECT_ID, location="us-central1")
```

❌ **错误 3：忘记 OAuth 认证**
```python
# 错误：直接使用会认证失败
vertexai.init(project=GCP_PROJECT_ID, ...)

# 正确：先进行 OAuth 认证
from google.colab import auth
auth.authenticate_user()  # ← 必须先执行这一步
vertexai.init(project=GCP_PROJECT_ID, ...)
```

---

## 快速开始

> 💡 **选择你的环境**：以下提供**本地环境**和 **Colab** 两种使用方式，**API 调用完全相同**，只是认证方式不同。

---

### 方式 1：本地环境完整示例（推荐）

#### 步骤 1：创建项目文件

创建 `virtual_tryon.py`：

```python
import os
import cv2
import numpy as np
from PIL import Image as PILImage
from matplotlib import pyplot as plt
from google import genai
from google.genai import types
import vertexai
from vertexai.preview.vision_models import (
    ImageGenerationModel,
    Image,
    RawReferenceImage,
    MaskReferenceImage,
)

# ═══════════════════════════════════════════════════════════
# 配置认证
# ═══════════════════════════════════════════════════════════
# 方法 1：从环境变量读取
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')

# 方法 2：直接硬编码（不推荐用于生产）
# GEMINI_API_KEY = "你的Gemini_API密钥"
# GCP_PROJECT_ID = "你的GCP项目ID"

# 初始化 Gemini API
client = genai.Client(api_key=GEMINI_API_KEY)

# 初始化 Vertex AI（需要先配置 gcloud 认证）
vertexai.init(project=GCP_PROJECT_ID, location="us-central1")

print("✅ API 认证配置完成")

# ═══════════════════════════════════════════════════════════
# 核心函数（与 Colab 版本完全相同）
# ═══════════════════════════════════════════════════════════

def parse_json(text: str) -> str:
    return text.strip().removeprefix("```json").removesuffix("```")

def generate_mask(predicted_str: str, *, img_height: int, img_width: int):
    """生成分割掩码（完整实现见原文档）"""
    # ... 完整代码见文档核心功能详解部分
    pass

def create_binary_mask_overlay(img, segmentation_data, alpha=0.8):
    """创建二值掩码（完整实现见原文档）"""
    # ... 完整代码见文档核心功能详解部分
    pass

# ═══════════════════════════════════════════════════════════
# 使用示例
# ═══════════════════════════════════════════════════════════

# 1. 图像分割
input_image = "person.jpg"
object_to_segment = "hoodie"

img = PILImage.open(input_image)
img_height, img_width = img.size[1], img.size[0]

prompt = f"Give the segmentation masks for {object_to_segment}..."
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[prompt, img],
    config=types.GenerateContentConfig(temperature=0.5)
)

segmentation_data = generate_mask(response.text, img_height=img_height, img_width=img_width)
binary_mask = create_binary_mask_overlay(img, segmentation_data)
cv2.imwrite("mask.png", binary_mask)

print("✅ 分割掩码已生成")

# 2. 虚拟试衣
edit_model = ImageGenerationModel.from_pretrained("imagen-3.0-capability-001")

edited_image = edit_model.edit_image(
    prompt="A dark green jacket, white shirt inside",
    edit_mode='inpainting-insert',
    reference_images=[
        RawReferenceImage(image=Image.load_from_file(input_image), reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=Image.load_from_file("mask.png"),
            mask_mode='foreground',
            dilation=0.02
        )
    ],
    number_of_images=1,
    safety_filter_level="block_some",
    person_generation="allow_adult"
)

edited_image[0].save("result.png")
print("✅ 虚拟试衣完成，结果已保存到 result.png")
```

#### 步骤 2：配置环境变量

```bash
# Linux/macOS
export GOOGLE_API_KEY="你的Gemini_API密钥"
export GCP_PROJECT_ID="你的GCP项目ID"

# Windows PowerShell
$env:GOOGLE_API_KEY="你的Gemini_API密钥"
$env:GCP_PROJECT_ID="你的GCP项目ID"
```

#### 步骤 3：配置 GCP 认证

```bash
# 安装 gcloud CLI
# 访问：https://cloud.google.com/sdk/docs/install

# 登录并设置默认凭证
gcloud auth application-default login
```

#### 步骤 4：运行程序

```bash
python virtual_tryon.py
```

---

### 方式 2：Google Colab 快速开始

#### 步骤 1：导入库和认证

```python
import cv2
import numpy as np
from PIL import Image as PILImage
from matplotlib import pyplot as plt
from google import genai
from google.genai import types
import random
import base64
from IPython.display import Markdown, HTML
from base64 import b64encode
import json
import io
from io import BytesIO

# Google Colab 认证
from google.colab import userdata, auth
auth.authenticate_user()

# Vertex AI 导入
import vertexai
from vertexai.preview.vision_models import (
    ControlReferenceImage,
    Image,
    ImageGenerationModel,
    MaskReferenceImage,
    RawReferenceImage,
)
```

### 步骤 2：配置 API 密钥和项目

```python
# 配置 Gemini API 密钥
GEMINI_API_KEY = userdata.get('GOOGLE_API_KEY')
client = genai.Client(api_key=GEMINI_API_KEY)

# 配置 GCP 项目 ID
GCP_PROJECT_ID = userdata.get('GCP_PROJECT_ID')

# 选择 Gemini 模型
MODEL_ID = "gemini-3-flash-preview"  # 可选其他模型
```

### 步骤 3：准备图像

```python
# 下载示例图像（或使用自己的图像）
!wget -q https://storage.googleapis.com/generativeai-downloads/images/Virtual_try_on_person.png -O /content/image_01.png

# 设置图像路径
input_image = 'image_01.png'
image_path = f"/content/{input_image}"
```

### 步骤 4：使用 Gemini 2.5 生成分割掩码

```python
# 指定要分割的物体
object_to_segment = 'hoodie'  # 可以是 'jacket', 'shirt', 'pants' 等

# 构建提示词
prompt = f"Give the segmentation masks for {object_to_segment}. Output a JSON list of segmentation masks where each entry contains the 2D bounding box in the key 'box_2d', the segmentation mask in key 'mask', and the text label in the key 'label'."

# 加载图像
img = PILImage.open(image_path)
img_height, img_width = img.size[1], img.size[0]

# 调用 Gemini 2.5 生成掩码
response = client.models.generate_content(
    model=MODEL_ID,
    contents=[prompt, img],
    config=types.GenerateContentConfig(
        temperature=0.5,
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
        ],
    )
)

# 解析响应并生成掩码
result = response.text
segmentation_data = generate_mask(result, img_height=img_height, img_width=img_width)

# 创建二值掩码
if segmentation_data:
    binary_mask = create_binary_mask_overlay(img, segmentation_data, alpha=0.8)
    cv2.imwrite(f"annotation_mask_{input_image}", binary_mask)
else:
    print("未找到分割掩码")
```

### 步骤 5：配置 Imagen 3 编辑参数

```python
# 配置文件路径
mask_file = f"/content/annotation_mask_{input_image}"
output_file = f"/content/output_{input_image}"

# 配置编辑提示词（描述要替换的服装）
prompt = "A dark green jacket, white shirt inside it"

# 配置编辑模式和掩码参数
edit_mode = 'inpainting-insert'  # 插入模式
mask_mode = 'foreground'         # 前景模式
dilation = 0.01                  # 掩码膨胀系数（0-1）
```

### 步骤 6：使用 Imagen 3 生成编辑后的图像

```python
# 初始化 Vertex AI
vertexai.init(project=GCP_PROJECT_ID, location="us-central1")

# 加载 Imagen 3 模型
edit_model = ImageGenerationModel.from_pretrained("imagen-3.0-capability-001")

# 加载图像
base_img = Image.load_from_file(location=image_path)
mask_img = Image.load_from_file(location=mask_file)

# 创建参考图像
raw_ref_image = RawReferenceImage(image=base_img, reference_id=0)
mask_ref_image = MaskReferenceImage(
    reference_id=1,
    image=mask_img,
    mask_mode=mask_mode,
    dilation=dilation
)

# 生成编辑后的图像
edited_image = edit_model.edit_image(
    prompt=prompt,
    edit_mode=edit_mode,
    reference_images=[raw_ref_image, mask_ref_image],
    number_of_images=1,
    safety_filter_level="block_some",
    person_generation="allow_adult",
)

# 保存结果
edited_image[0].save(output_file)

# 显示结果
output_img = PILImage.open(output_file)
display(output_img)
```

---

## 核心功能详解

### 1. 分割掩码生成

#### 系统指令

```python
bounding_box_system_instructions = """
    Return bounding boxes as a JSON array with labels. Never return masks or code fencing. Limit to 25 objects.
    If an object is present multiple times, name them according to their unique characteristic (colors, size, position, unique characteristics, etc..).
"""
```

#### 掩码处理函数

##### parse_json(text: str)
移除 JSON 字符串中的代码围栏标记。

```python
def parse_json(text: str) -> str:
    return text.strip().removeprefix("```json").removesuffix("```")
```

##### generate_mask(predicted_str, img_height, img_width)
核心掩码生成函数，处理 Gemini 返回的 JSON 数据并生成完整的分割掩码。

**处理流程**：
1. 解析 JSON 响应
2. 遍历每个分割对象
3. 解码 base64 编码的掩码图像
4. 将归一化坐标（0-1000）转换为绝对像素坐标
5. 调整掩码大小以匹配边界框
6. 将掩码放置到完整图像的正确位置
7. 返回分割数据列表

**错误处理**：
- 跳过无效的 JSON 结构
- 处理解码失败的掩码
- 处理无效的边界框坐标
- 尺寸不匹配时尝试自动修正

##### create_binary_mask_overlay(img, segmentation_data, alpha)
合并多个分割掩码为单一二值掩码。

**参数**：
- `img`：原始图像
- `segmentation_data`：分割数据列表（来自 generate_mask）
- `alpha`：透明度（未使用，保留用于扩展）

**返回**：
- 二值掩码图像（NumPy 数组），白色（255）表示前景，黑色（0）表示背景

### 2. 图像编辑参数配置

#### 编辑模式（edit_mode）

| 模式 | 描述 | 使用场景 |
|------|------|----------|
| `inpainting-insert` | 在掩码区域插入新内容 | 替换服装、添加配饰 |
| `inpainting-remove` | 移除掩码区域的内容 | 移除物体、清理背景 |
| `outpainting` | 扩展图像边界（不改变分辨率） | 扩展画布、补全被裁剪内容 |

> **注意**：`outpainting` 是扩展画布，**不是超分辨率**。如需提高图像分辨率，请参见下方的"图像超分辨率"部分。

#### 掩码模式（mask_mode）

| 模式 | 描述 | 使用场景 |
|------|------|----------|
| `foreground` | 编辑前景（白色掩码区域） | 替换主体物体 |
| `background` | 编辑背景（黑色掩码区域） | 更换背景环境 |

#### 膨胀系数（dilation）

- **范围**：0.0 - 1.0
- **作用**：控制掩码边缘的扩张或收缩
- **用途**：
  - `dilation > 0`：扩大掩码区域，确保完全覆盖目标物体
  - `dilation = 0`：使用原始掩码大小
  - 建议值：0.01 - 0.05（根据实际效果调整）

#### 其他参数

```python
# 生成图像数量
number_of_images=1  # 1-4张

# 安全过滤级别
safety_filter_level="block_some"  # "block_none", "block_some", "block_most"

# 人物生成控制
person_generation="allow_adult"  # "dont_allow", "allow_adult"
```

### 3. 图像超分辨率（Upscale）

除了虚拟试衣，Vertex AI 还提供了**专门的超分辨率模型**来提高图像分辨率和质量。

#### 模型信息

- **模型名称**：`imagen-4.0-upscale-preview`（预览版）
- **功能**：提高图像分辨率而不损失质量
- **状态**：Preview（2025年1月）

#### 使用方法

```python
from vertexai.preview.vision_models import ImageGenerationModel, Image

# 初始化 Vertex AI
vertexai.init(project=GCP_PROJECT_ID, location="us-central1")

# 加载超分辨率模型
upscale_model = ImageGenerationModel.from_pretrained("imagen-4.0-upscale-preview")

# 加载原始图像
input_image = Image.load_from_file("original.png")

# 执行超分辨率处理
upscaled_images = upscale_model.upscale_image(
    image=input_image,
    upscale_factor=2,      # 2x 或 4x
    add_watermark=False    # 是否添加数字水印（默认 True）
)

# 保存高分辨率图像
upscaled_images[0].save("upscaled_2x.png")
```

#### 参数说明

| 参数 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| `image` | Image | 输入图像对象 | - |
| `upscale_factor` | int | 放大倍数 | `2` 或 `4` |
| `add_watermark` | bool | 是否添加数字水印 | `True`（默认）或 `False` |

#### 重要限制

⚠️ **分辨率限制**：输出图像分辨率（输入分辨率 × 放大倍数）**不能超过 17 megapixels**

**计算示例**：

```python
# ✅ 安全范围
# 输入：512×512 = 0.26MP
# 2x 放大：1024×1024 = 1.05MP ✅
# 4x 放大：2048×2048 = 4.19MP ✅

# ✅ 接近上限
# 输入：2048×2048 = 4.19MP
# 2x 放大：4096×4096 = 16.78MP ✅

# ❌ 超过限制
# 输入：2048×2048 = 4.19MP
# 4x 放大：8192×8192 = 67.11MP ❌ 超过 17MP

# ❌ 超过限制
# 输入：4000×4000 = 16MP
# 2x 放大：8000×8000 = 64MP ❌ 超过 17MP
```

#### 完整工作流：虚拟试衣 + 超分辨率

```python
# 步骤 1：虚拟试衣（生成 1024×1024 图像）
edited_image = edit_model.edit_image(
    prompt="A dark green jacket",
    edit_mode='inpainting-insert',
    reference_images=[raw_ref_image, mask_ref_image],
    number_of_images=1
)
edited_image[0].save("try_on_result.png")

# 步骤 2：超分辨率处理（放大到 4096×4096）
upscale_model = ImageGenerationModel.from_pretrained("imagen-4.0-upscale-preview")
upscaled = upscale_model.upscale_image(
    image=Image.load_from_file("try_on_result.png"),
    upscale_factor=4,
    add_watermark=False
)
upscaled[0].save("try_on_result_4k.png")

print("虚拟试衣完成，已生成 4K 高清图像！")
```

#### Outpainting vs Upscale 对比

| 功能 | Outpainting | Upscale |
|------|-------------|---------|
| **目的** | 扩展画布边界 | 提高分辨率 |
| **分辨率变化** | 宽/高增加，像素密度不变 | 宽/高成倍增加，像素密度提高 |
| **示例** | 512×512 → 512×768（扩展高度） | 512×512 → 2048×2048（4倍放大） |
| **使用场景** | 补全被裁剪内容、扩展背景 | 提高清晰度、打印大尺寸 |
| **模型** | imagen-3.0-capability-001 | imagen-4.0-upscale-preview |

### 4. 画布扩展（Outpainting）详解

Outpainting 能够在原始图像的**边界之外**生成新内容，就像画家在画布边缘继续作画。

#### 工作原理

```
原始图像（512×512）          Outpainting 结果（512×768）
┌─────────────┐               ┌─────────────┐
│             │               │             │
│  人物半身   │  ──扩展→      │  人物半身   │
│    照片     │               │    照片     │
└─────────────┘               ├─────────────┤
                              │  AI 生成的  │
                              │  下半身和   │
                              │   背景      │
                              └─────────────┘
```

#### 应用场景示例

##### 场景 1：补全被裁剪的全身照

```python
from vertexai.preview.vision_models import ImageGenerationModel, Image
import numpy as np
from PIL import Image as PILImage

# 1. 创建扩展掩码（底部扩展 256 像素）
original_height, original_width = 512, 512
expand_height = 256

# 创建掩码：原图区域 = 黑色(0)，扩展区域 = 白色(255)
new_height = original_height + expand_height
mask = np.zeros((new_height, original_width), dtype=np.uint8)
mask[original_height:, :] = 255  # 底部扩展区域
PILImage.fromarray(mask).save("expand_bottom_mask.png")

# 2. 加载原始半身照并扩展画布
original_img = PILImage.open("halfbody.png")  # 512×512
expanded_canvas = PILImage.new('RGB', (original_width, new_height), (255, 255, 255))
expanded_canvas.paste(original_img, (0, 0))
expanded_canvas.save("expanded_canvas.png")

# 3. 执行 Outpainting
vertexai.init(project=GCP_PROJECT_ID, location="us-central1")
edit_model = ImageGenerationModel.from_pretrained("imagen-3.0-capability-001")

result = edit_model.edit_image(
    prompt="Complete the lower body with jeans and white sneakers, standing on wooden floor, natural lighting",
    edit_mode='outpainting',
    reference_images=[
        RawReferenceImage(image=Image.load_from_file("expanded_canvas.png"), reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=Image.load_from_file("expand_bottom_mask.png"),
            mask_mode='background',  # 扩展背景区域
            dilation=0.02
        )
    ],
    number_of_images=1,
    safety_filter_level="block_some",
    person_generation="allow_adult"
)

result[0].save("fullbody_result.png")
```

##### 场景 2：左右扩展背景

```python
# 创建左右扩展掩码（各扩展 128 像素）
expand_width = 128
new_width = original_width + expand_width * 2

# 掩码：左右两侧 = 白色(255)，中间原图 = 黑色(0)
mask = np.zeros((original_height, new_width), dtype=np.uint8)
mask[:, :expand_width] = 255          # 左侧扩展
mask[:, -expand_width:] = 255         # 右侧扩展
PILImage.fromarray(mask).save("expand_sides_mask.png")

# 扩展画布（左右各添加 128 像素）
expanded_canvas = PILImage.new('RGB', (new_width, original_height), (255, 255, 255))
expanded_canvas.paste(original_img, (expand_width, 0))  # 原图放在中间
expanded_canvas.save("expanded_canvas_sides.png")

# Outpainting
result = edit_model.edit_image(
    prompt="Extend with natural park scenery, trees and grass on both sides, maintaining soft daylight",
    edit_mode='outpainting',
    reference_images=[
        RawReferenceImage(image=Image.load_from_file("expanded_canvas_sides.png"), reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=Image.load_from_file("expand_sides_mask.png"),
            mask_mode='background',
            dilation=0.03
        )
    ],
    number_of_images=1
)

result[0].save("wide_background_result.png")  # 768×512
```

##### 场景 3：虚拟试衣 + 画布扩展组合

```python
# 完整工作流：先换衣服，再扩展全身

# 步骤 1：虚拟试衣（替换上衣 - 原尺寸 512×512）
try_on_result = edit_model.edit_image(
    prompt="A stylish navy blue blazer, professional office wear",
    edit_mode='inpainting-insert',
    reference_images=[
        RawReferenceImage(image=Image.load_from_file("person.png"), reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=Image.load_from_file("upper_body_mask.png"),
            mask_mode='foreground',
            dilation=0.02
        )
    ],
    number_of_images=1
)
try_on_result[0].save("try_on_blazer.png")

# 步骤 2：画布扩展（补全下半身 512×512 → 512×768）
# 创建扩展掩码
expanded_height = 768
mask = np.zeros((expanded_height, 512), dtype=np.uint8)
mask[512:, :] = 255
PILImage.fromarray(mask).save("expand_mask.png")

# 扩展画布
try_on_img = PILImage.open("try_on_blazer.png")
expanded = PILImage.new('RGB', (512, expanded_height), (255, 255, 255))
expanded.paste(try_on_img, (0, 0))
expanded.save("expanded_try_on.png")

# Outpainting
final_result = edit_model.edit_image(
    prompt="Complete full body with matching black dress pants and leather shoes, office environment background",
    edit_mode='outpainting',
    reference_images=[
        RawReferenceImage(image=Image.load_from_file("expanded_try_on.png"), reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=Image.load_from_file("expand_mask.png"),
            mask_mode='background',
            dilation=0.03
        )
    ],
    number_of_images=1,
    person_generation="allow_adult"
)

final_result[0].save("fullbody_with_blazer.png")
```

#### 掩码制作辅助函数

```python
def create_outpainting_mask(
    original_size: tuple,
    direction: str,
    expand_pixels: int
) -> np.ndarray:
    """
    创建 Outpainting 掩码

    Args:
        original_size: (width, height) 原始图像尺寸
        direction: 'bottom', 'top', 'left', 'right', 'all'
        expand_pixels: 扩展的像素数

    Returns:
        掩码数组和新尺寸
    """
    width, height = original_size

    if direction == 'bottom':
        new_size = (width, height + expand_pixels)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[height:, :] = 255

    elif direction == 'top':
        new_size = (width, height + expand_pixels)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:expand_pixels, :] = 255

    elif direction == 'left':
        new_size = (width + expand_pixels, height)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:, :expand_pixels] = 255

    elif direction == 'right':
        new_size = (width + expand_pixels, height)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:, -expand_pixels:] = 255

    elif direction == 'all':
        new_size = (width + expand_pixels * 2, height + expand_pixels * 2)
        mask = np.zeros(new_size[::-1], dtype=np.uint8)
        mask[:expand_pixels, :] = 255  # 上
        mask[-expand_pixels:, :] = 255  # 下
        mask[:, :expand_pixels] = 255  # 左
        mask[:, -expand_pixels:] = 255  # 右

    return mask, new_size

# 使用示例
mask, new_size = create_outpainting_mask(
    original_size=(512, 512),
    direction='bottom',
    expand_pixels=256
)
PILImage.fromarray(mask).save("auto_mask.png")
```

#### Outpainting 提示词最佳实践

```python
# ✅ 好的提示词（详细、风格一致）
prompt = """
Continue the outdoor scene with lush green grass,
scattered trees in the background, natural daylight from the left,
soft shadows, photorealistic style matching the upper portion
"""

# ❌ 不好的提示词（模糊、不连贯）
prompt = "more stuff below"

# ✅ 人物扩展（详细描述下半身）
prompt = """
Complete the lower body with slim-fit dark jeans,
brown leather belt, white canvas sneakers,
standing on a hardwood floor, maintaining the same lighting
"""

# ✅ 背景扩展（保持一致性）
prompt = """
Extend the cafe interior on both sides,
wooden furniture, warm ambient lighting,
blurred background for depth of field
"""
```

#### 重要注意事项

1. **扩展比例建议**
   - 单次扩展不宜超过原图的 50%（例如 512×512 → 512×768）
   - 过大的扩展可能导致质量下降和不连贯

2. **画布准备**
   - 必须先手动扩展画布（添加白色或适当颜色的区域）
   - 原图放置在正确位置（扩展方向的相反侧）

3. **掩码颜色**
   - 白色（255）= 要生成的新区域
   - 黑色（0）= 保留的原图区域

4. **渐进式扩展**
   ```python
   # 如果需要大幅扩展，分多次进行
   # 第 1 次：512×512 → 512×640 (扩展 128px)
   # 第 2 次：512×640 → 512×768 (再扩展 128px)
   # 这样可以保持更好的连贯性
   ```

#### 三种编辑模式完整对比

| 特性 | Inpainting-Insert | Inpainting-Remove | Outpainting |
|------|-------------------|-------------------|-------------|
| **改变区域** | 掩码内部 | 掩码内部 | 画布边界外 |
| **掩码模式** | foreground | foreground | background |
| **画布尺寸** | 不变 | 不变 | 扩大 |
| **像素密度** | 不变 | 不变 | 不变 |
| **典型用途** | 替换服装、物体 | 移除物体 | 补全裁剪、扩展背景 |
| **虚拟试衣** | ✅ 主要用途 | ❌ 不适用 | ✅ 补全全身 |

---

## 最佳实践

### 1. 提示词编写

#### 分割提示词
- **准确性**：使用具体的物体描述
  - ✅ 好：`"hoodie"`, `"blue denim jacket"`, `"white t-shirt"`
  - ❌ 差：`"clothes"`, `"stuff"`, `"thing"`

- **唯一性**：当有多个相似物体时，使用颜色、位置等特征区分
  - ✅ 好：`"red hoodie"`, `"person on the left's jacket"`
  - ❌ 差：`"hoodie"`（当图像中有多个连帽衫时）

#### 编辑提示词
- **详细描述**：提供完整的服装描述
  - ✅ 好：`"A dark green puffer jacket with orange lining, white crew neck t-shirt underneath"`
  - ❌ 差：`"jacket"`

- **风格一致**：描述应与原图像风格一致
  - 包含光照信息：`"A black leather jacket with natural lighting"`
  - 包含质感信息：`"A soft cashmere sweater, ribbed texture"`

- **上下文关系**：描述与周围环境的关系
  - `"A formal suit jacket matching the indoor office setting"`

### 2. 掩码优化

#### 可视化检查
在应用编辑前，务必可视化检查掩码质量：

```python
# 可视化原图和掩码
fig, axes = plt.subplots(1, 2, figsize=(12, 6))
axes[0].imshow(img)
axes[0].set_title("原始图像")
axes[0].axis('off')
axes[1].imshow(binary_mask, cmap='gray')
axes[1].set_title("分割掩码")
axes[1].axis('off')
plt.show()
```

#### 掩码调整技巧
1. **边缘处理**：
   - 如果掩码边缘不够平滑，增加 `dilation` 值
   - 如果掩码超出目标范围，减小 `dilation` 值

2. **精度控制**：
   - 使用更精确的分割提示词
   - 尝试不同的 Gemini 模型（pro 版本通常更精确）

3. **多次尝试**：
   - Gemini 的分割结果可能有变化，可以多次调用选择最佳结果

### 3. 参数调优

#### 推荐配置组合

**休闲服装替换**：
```python
edit_mode = 'inpainting-insert'
mask_mode = 'foreground'
dilation = 0.02
prompt = "A casual denim jacket, light blue color, relaxed fit"
```

**正式服装替换**：
```python
edit_mode = 'inpainting-insert'
mask_mode = 'foreground'
dilation = 0.01
prompt = "A tailored navy blue blazer, professional style, sharp creases"
```

**服装移除**：
```python
edit_mode = 'inpainting-remove'
mask_mode = 'foreground'
dilation = 0.03
prompt = "Natural skin tone, smooth texture"
```

### 4. 性能优化

#### 图像尺寸
- **建议尺寸**：1024x1024 或更小
- **过大图像**：可能导致处理时间过长或内存不足
- **预处理**：
  ```python
  # 调整图像大小
  max_size = 1024
  img = PILImage.open(image_path)
  if max(img.size) > max_size:
      ratio = max_size / max(img.size)
      new_size = tuple([int(x * ratio) for x in img.size])
      img = img.resize(new_size, PILImage.Resampling.LANCZOS)
  ```

#### API 配额管理
- Gemini API 和 Vertex AI 都有配额限制
- 建议在测试阶段使用较小的图像和较少的生成数量
- 生产环境中需要申请更高的配额

#### 批处理
如果需要处理多张图像，可以考虑：
```python
# 批量处理图像
image_list = ['image_01.png', 'image_02.png', 'image_03.png']
for input_image in image_list:
    # 执行分割和编辑流程
    pass
```

---

## 常见问题

### Q1: Gemini 无法生成准确的分割掩码

**可能原因**：
- 提示词不够具体
- 图像质量较差
- 目标物体与背景对比度低

**解决方案**：
1. 使用更具体的描述：
   ```python
   # 不好
   object_to_segment = 'clothes'

   # 好
   object_to_segment = 'red hoodie with white drawstrings'
   ```

2. 尝试更高级的模型：
   ```python
   MODEL_ID = "gemini-2.5-pro"  # 使用 Pro 版本
   ```

3. 调整温度参数：
   ```python
   temperature=0.2  # 降低温度以获得更确定的结果
   ```

### Q2: Imagen 3 生成的图像不自然

**可能原因**：
- 掩码边缘不够平滑
- 提示词与原图风格不匹配
- 编辑区域过大

**解决方案**：
1. 调整膨胀系数：
   ```python
   dilation = 0.03  # 稍微扩大掩码以获得更好的融合
   ```

2. 改进提示词，包含光照和风格信息：
   ```python
   prompt = "A dark blue jacket, natural daylight, soft shadows, photorealistic style"
   ```

3. 分步编辑：对于复杂的替换，可以分多次进行小范围编辑

### Q3: 生成速度很慢

**可能原因**：
- 图像分辨率过高
- 网络延迟
- API 配额限制

**解决方案**：
1. 调整图像大小（见上文性能优化部分）
2. 使用更快的模型：
   ```python
   MODEL_ID = "gemini-2.5-flash-lite"
   ```
3. 检查网络连接和 API 配额状态

### Q4: 出现 "Invalid mask format" 错误

**可能原因**：
- Gemini 返回的 JSON 格式不正确
- 掩码解码失败

**解决方案**：
1. 检查 Gemini 响应：
   ```python
   print(response.text)  # 查看原始响应
   ```

2. 添加更详细的错误日志：
   ```python
   # generate_mask 函数会打印详细的错误信息
   # 检查控制台输出
   ```

3. 重新调用 Gemini API（可能是临时问题）

### Q5: 编辑后的图像有明显的接缝

**可能原因**：
- 掩码边缘过于锐利
- 膨胀系数设置不当

**解决方案**：
1. 增加膨胀系数：
   ```python
   dilation = 0.05  # 扩大融合区域
   ```

2. 在提示词中强调"seamless" 或 "natural transition"：
   ```python
   prompt = "A green jacket with seamless blending, natural transition to skin"
   ```

---

## 完整示例

### 示例 1：基础服装替换

```python
# 1. 配置
input_image = 'person.jpg'
object_to_segment = 'jacket'
replacement_prompt = "A red leather jacket, punk style, silver zippers"

# 2. 生成掩码
prompt = f"Give the segmentation masks for {object_to_segment}..."
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[prompt, PILImage.open(input_image)],
    config=types.GenerateContentConfig(temperature=0.5)
)
segmentation_data = generate_mask(response.text, img_height, img_width)
binary_mask = create_binary_mask_overlay(img, segmentation_data)
cv2.imwrite("mask.png", binary_mask)

# 3. 编辑图像
edit_model = ImageGenerationModel.from_pretrained("imagen-3.0-capability-001")
edited_image = edit_model.edit_image(
    prompt=replacement_prompt,
    edit_mode='inpainting-insert',
    reference_images=[
        RawReferenceImage(image=Image.load_from_file(input_image), reference_id=0),
        MaskReferenceImage(
            reference_id=1,
            image=Image.load_from_file("mask.png"),
            mask_mode='foreground',
            dilation=0.02
        )
    ],
    number_of_images=1,
    safety_filter_level="block_some",
    person_generation="allow_adult"
)
edited_image[0].save("output.png")
```

### 示例 2：批量服装变换

```python
# 定义多个服装样式
styles = [
    "A casual denim jacket, light blue wash",
    "A formal black blazer, slim fit",
    "A sporty windbreaker, neon colors",
    "A vintage bomber jacket, brown leather"
]

# 批量生成
for i, style in enumerate(styles):
    edited_image = edit_model.edit_image(
        prompt=style,
        edit_mode='inpainting-insert',
        reference_images=[raw_ref_image, mask_ref_image],
        number_of_images=1,
        safety_filter_level="block_some",
        person_generation="allow_adult"
    )
    edited_image[0].save(f"output_style_{i}.png")
    print(f"生成样式 {i+1}: {style}")
```

### 示例 3：多物体分割和编辑

```python
# 分割多个物体
objects_to_segment = "hoodie and pants"

prompt = f"Give the segmentation masks for {objects_to_segment}..."
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[prompt, img],
    config=types.GenerateContentConfig(temperature=0.5)
)

segmentation_data = generate_mask(response.text, img_height, img_width)

# 为不同物体生成独立掩码
for mask, label in segmentation_data:
    print(f"检测到: {label}")
    # 保存独立掩码
    cv2.imwrite(f"mask_{label}.png", mask)

# 分别编辑每个物体
# ... 使用对应的掩码文件进行编辑
```

---

## 技术细节

### 坐标系统转换

Gemini 返回的边界框坐标是归一化的（0-1000 范围），需要转换为绝对像素坐标：

```python
# 归一化坐标（0-1000）
y0_norm, x0_norm, y1_norm, x1_norm = box

# 转换为绝对坐标
abs_y0 = int(y0_norm / 1000.0 * img_height)
abs_x0 = int(x0_norm / 1000.0 * img_width)
abs_y1 = int(y1_norm / 1000.0 * img_height)
abs_x1 = int(x1_norm / 1000.0 * img_width)
```

### 掩码调整流程

```python
# 1. 解码 base64 掩码
png_bytes = base64.b64decode(png_str.removeprefix("data:image/png;base64,"))
bbox_mask = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)

# 2. 调整掩码大小以匹配边界框
bbox_width = abs_x1 - abs_x0
bbox_height = abs_y1 - abs_y0
resized_bbox_mask = cv2.resize(bbox_mask, (bbox_width, bbox_height))

# 3. 放置到完整图像掩码中
full_mask = np.zeros((img_height, img_width), dtype=np.uint8)
full_mask[abs_y0:abs_y1, abs_x0:abs_x1] = resized_bbox_mask
```

### JSON 响应格式

Gemini 2.5 返回的 JSON 格式示例：

```json
[
  {
    "box_2d": [100, 200, 800, 600],
    "mask": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "label": "red hoodie"
  }
]
```

---

## 与旧版本的区别

### SAM 2.1 版本（旧）
- 需要单独运行 SAM 2.1 模型
- 需要更多的计算资源
- 需要额外的模型权重下载
- 分割流程更复杂

### Gemini 2.5 版本（新）
- 直接通过 API 调用，无需本地模型
- 计算在云端完成，无需本地 GPU
- 工作流程更简化
- 更易于集成到其他应用中

---

## 故障排除

### API 认证问题
```python
# 错误：Invalid API key
# 解决：检查 Colab Secrets 配置
GEMINI_API_KEY = userdata.get('GOOGLE_API_KEY')
print(f"API Key 长度: {len(GEMINI_API_KEY)}")  # 应该不为 0
```

### Vertex AI 初始化失败
```python
# 错误：Project not found
# 解决：确认项目 ID 正确
GCP_PROJECT_ID = userdata.get('GCP_PROJECT_ID')
print(f"Project ID: {GCP_PROJECT_ID}")

# 检查 Vertex AI API 是否启用
# 访问：https://console.cloud.google.com/apis/library/aiplatform.googleapis.com
```

### 内存不足
```python
# 错误：Out of memory
# 解决：减小图像尺寸或使用 Colab Pro
max_size = 512  # 降低分辨率
```

---

## 扩展应用

### 1. 虚拟化妆
```python
object_to_segment = 'lips'
prompt = "Red lipstick, matte finish, natural look"
```

### 2. 发型变换
```python
object_to_segment = 'hair'
prompt = "Short curly hair, dark brown color, voluminous"
```

### 3. 配饰添加
```python
object_to_segment = 'face'
prompt = "Aviator sunglasses, gold frame, reflective lenses"
```

### 4. 背景替换
```python
edit_mode = 'inpainting-insert'
mask_mode = 'background'  # 编辑背景
prompt = "Professional studio background, white backdrop, soft lighting"
```

---

## 参考资料

### 官方文档
- [Gemini API 文档](https://ai.google.dev/docs)
- [Vertex AI Imagen 文档](https://cloud.google.com/vertex-ai/docs/generative-ai/image/overview)
- [Vertex AI Python SDK](https://cloud.google.com/python/docs/reference/aiplatform/latest)

### 相关资源
- [Google AI Studio](https://aistudio.google.com/)
- [Vertex AI 控制台](https://console.cloud.google.com/vertex-ai)
- [Gemini Cookbook](https://github.com/google-gemini/cookbook)

### 社区贡献
- 原作者：[Nitin Tiwari](https://github.com/NSTiwari)
- [LinkedIn](https://linkedin.com/in/tiwari-nitin)
- [更多示例](https://github.com/search?q=repo%3Agoogle-gemini%2Fcookbook%20%22This%20notebook%20was%20contributed%20by%20Nitin%20Tiwari%22&type=code)

### 旧版本（SAM 2.1）
- [Virtual Try-On with SAM 2.1](https://github.com/NSTiwari/Virtual-Try-On-Imagen3/blob/main/Virtual_Try_On_Imagen3.ipynb)

---

## 许可证

Copyright 2025 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

## 更新日志

- **2025-01**: 首次发布，使用 Gemini 2.5 替代 SAM 2.1
- 简化了工作流程
- 提高了分割精度
- 减少了依赖库

---

## 贡献

欢迎贡献改进和新功能！如果您有很酷的 Gemini 示例，欢迎[分享](https://github.com/google-gemini/cookbook/blob/main/CONTRIBUTING.md)。

---

**本文档由 Claude Code 生成，基于 Virtual_Try_On.ipynb 笔记本分析而成。**
