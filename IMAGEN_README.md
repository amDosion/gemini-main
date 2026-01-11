# 🎨 Imagen API - 双模式图像生成

支持 Gemini API 和 Vertex AI 两种模式,提供灵活的图像生成能力。

## 🔒 最新更新 (2026-01-09)

### 安全性改进
- ✅ **API Key 不再从前端传递** - 提高安全性，防止密钥泄露
- ✅ **Session-based 认证** - 使用 session cookie 进行身份验证
- ✅ **用户级配置** - 支持每个用户独立配置 Vertex AI
- ✅ **配置优先级** - 数据库配置 → 环境变量（自动回退）

### 架构改进
- ✅ **完整的用户上下文传递** - Router → ProviderFactory → GoogleService → ImageGenerator → ImagenCoordinator
- ✅ **增强的错误处理** - 友好的认证错误消息
- ✅ **监控和日志** - 使用统计、回退次数追踪
- ✅ **遗留代码标注** - 清晰标记旧代码路径

**迁移指南**: 参考 [IMAGEN_API_MIGRATION.md](IMAGEN_API_MIGRATION.md)

---

## ✨ 特性

### Gemini API 模式 (默认)
- ✅ 简单易用,只需 API Key
- ✅ 快速开始,无需额外配置
- ✅ 支持基础图像生成参数

### Vertex AI 模式 (高级)
- ✅ 更多 `person_generation` 选项 (`DONT_ALLOW`, `ALLOW_ADULT`, `ALLOW_ALL`)
- ✅ `negative_prompt` - 负面提示词,排除不想要的元素
- ✅ `seed` - 随机种子,生成可复现的结果
- ✅ `add_watermark` - 添加水印
- ✅ `enhance_prompt` - 自动优化提示词
- ✅ `labels` - 自定义标签

## 🚀 快速开始

### Gemini API 模式

```python
from app.services.gemini.sdk_initializer import SDKInitializer
from app.services.gemini.image_generator import ImageGenerator

# 使用 API Key
sdk_init = SDKInitializer(api_key="YOUR_API_KEY")
generator = ImageGenerator(sdk_init)

result = await generator.generate_image(
    prompt="Red skateboard",
    model="imagen-4.0-generate-001",
    number_of_images=1
)
```

### Vertex AI 模式

**前置条件**: 需要配置 Google Cloud 认证

```python
# 使用 Vertex AI
sdk_init = SDKInitializer(
    use_vertex_ai=True,
    project_id="gen-lang-client-0639481221",
    location="us-central1"
)
generator = ImageGenerator(sdk_init)

result = await generator.generate_image(
    prompt="Red skateboard",
    model="imagen-4.0-generate-001",
    person_generation="DONT_ALLOW",  # ✅ 阻止生成人物
    negative_prompt="human",         # ✅ Vertex AI 专属
    seed=42                          # ✅ Vertex AI 专属
)
```

## 📋 参数对比

| 参数 | Gemini API | Vertex AI |
|------|-----------|-----------|
| `number_of_images` | ✅ | ✅ |
| `aspect_ratio` | ✅ | ✅ |
| `image_size` | ✅ | ✅ |
| `guidance_scale` | ✅ | ✅ |
| `person_generation` (DONT_ALLOW) | ✅ | ✅ |
| `person_generation` (ALLOW_ADULT) | ✅ | ✅ |
| `person_generation` (ALLOW_ALL) | ✅ | ✅ |
| `negative_prompt` | ❌ | ✅ |
| `seed` | ❌ | ✅ |
| `add_watermark` | ❌ | ✅ |
| `enhance_prompt` | ❌ | ✅ |

## 🔧 Vertex AI 配置

### 方法 1: 使用 gcloud CLI (推荐)

```bash
# 1. 安装 Google Cloud SDK
# 下载: https://cloud.google.com/sdk/docs/install

# 2. 配置认证
gcloud auth application-default login

# 3. 设置项目
gcloud config set project gen-lang-client-0639481221

# 4. 启用 API
gcloud services enable aiplatform.googleapis.com
```

### 方法 2: 使用服务账号密钥

1. 从 Google Cloud Console 下载服务账号密钥
2. 设置环境变量:
   ```bash
   set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\key.json
   ```

**详细配置**: 参考 `backend/VERTEX_AI_QUICKSTART.md`

## 🧪 测试

### Gemini API 测试
```bash
cd backend
python test_image_generation.py
```

**结果**: ✅ 5/5 测试通过

### Vertex AI 测试
```bash
cd backend
python test_vertex_ai.py
```

**注意**: 需要先配置认证

---

## � 监控

### 使用统计端点

查看 Vertex AI 和 Gemini API 的使用情况：

```bash
GET /api/generate/monitoring/stats
```

**响应示例**:
```json
{
  "status": "success",
  "stats": {
    "vertex_ai_usage": 150,
    "gemini_api_usage": 50,
    "fallback_count": 5
  },
  "description": {
    "vertex_ai_usage": "Number of times Vertex AI was used for image generation",
    "gemini_api_usage": "Number of times Gemini API was used for image generation",
    "fallback_count": "Number of times fallback from Vertex AI to Gemini API occurred"
  }
}
```

### 日志记录

系统会记录以下信息：
- 配置来源（数据库 vs 环境变量）
- 每次图片生成请求（用户、模型、参数）
- Vertex AI 回退事件
- 配置不完整警告

**日志位置**: 查看应用日志输出

---

## 📚 文档

- [快速开始指南](backend/VERTEX_AI_QUICKSTART.md) - 5 分钟配置
- [详细配置指南](backend/VERTEX_AI_SETUP.md) - 完整配置步骤
- [使用指南](backend/IMAGE_GENERATION_GUIDE.md) - API 使用说明
- [实施状态](.kiro/specs/erron/vertex-ai-implementation-status.md) - 开发进度
- [工作总结](.kiro/specs/erron/work-summary.md) - 完成的工作

## 🎯 当前状态

- ✅ 后端双模式实现完成
- ✅ Gemini API 测试通过
- ⏳ Vertex AI 等待认证配置
- ⏳ 前端界面待更新

## 🆘 需要帮助?

1. 查看 [快速开始指南](backend/VERTEX_AI_QUICKSTART.md)
2. 查看 [常见问题](backend/VERTEX_AI_SETUP.md#常见问题)
3. 运行 `python backend/test_vertex_ai.py` 查看详细错误

## 📝 许可

本项目使用 Google Gemini API 和 Vertex AI,请遵守相关服务条款。
