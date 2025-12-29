# 设计文档：万相（Wanx）图像生成模型支持

## 概述

本设计文档详细说明如何在项目中集成通义千问服务，以支持万相（Wanx）图像生成模型的完整功能。设计遵循现有架构模式，确保与项目其他部分的一致性。

## 系统架构

### 当前架构分析

**前端架构**：
```
用户界面 (Header.tsx)
    ↓
模型选择器 (useModels.ts)
    ↓
LLM 服务层 (llmService.ts)
    ↓
提供商工厂 (LLMFactory.ts)
    ↓
通义千问提供商 (DashScopeProvider.ts)
    ↓
DashScope API (直连)
```

**后端架构（目标）**：
```
前端请求
    ↓
FastAPI 路由层
    ↓
服务工厂/依赖注入
    ↓
QwenService (qwen.py)
    ↓
DashScope API
```

### 目标架构

**集成后的完整架构**：
```
前端 UI
    ↓
前端服务层 (llmService.ts)
    ↓ (选项1: 直连)        ↓ (选项2: 通过后端)
    ↓                      ↓
DashScope API  ←───  后端 API 路由
                          ↓
                    QwenService
                          ↓
                    DashScope API
```

**设计决策**：
- 保持前端直连 DashScope API 的能力（现有功能）
- 添加后端 API 路由作为可选路径
- 后端主要负责：
  1. 模型列表获取和缓存
  2. API 密钥验证
  3. 使用统计和成本计算
  4. 错误处理和日志记录

## 组件和接口设计

### 1. 后端服务集成

#### 1.1 服务注册

**文件**: `backend/app/services/__init__.py` 或 `backend/app/core/dependencies.py`

**设计**：
```python
from app.services.qwen import QwenService

# 服务工厂或依赖注入
def get_qwen_service(api_key: str, api_url: Optional[str] = None) -> QwenService:
    """获取通义千问服务实例"""
    return QwenService(
        api_key=api_key,
        api_url=api_url or QwenService.DEFAULT_BASE_URL
    )
```

#### 1.2 API 路由

**文件**: `backend/app/api/routes/qwen.py` (新建)

**端点设计**：

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/qwen/models` | GET | 获取模型列表 | - | `List[ModelInfo]` |
| `/api/qwen/validate` | POST | 验证 API 密钥 | `{api_key, api_url}` | `{valid: bool, models: List[str]}` |
| `/api/qwen/chat` | POST | 聊天接口 | `ChatRequest` | `ChatResponse` |
| `/api/qwen/image/generate` | POST | 图像生成 | `ImageGenRequest` | `ImageGenResponse` |

**接口定义**：
```python
# 模型信息
class ModelInfo(BaseModel):
    id: str
    name: str
    type: str  # "chat", "vision", "image-generation", "image-editing"
    context_length: int
    pricing: Dict[str, float]

# 验证请求
class ValidateRequest(BaseModel):
    api_key: str
    api_url: Optional[str] = None

# 验证响应
class ValidateResponse(BaseModel):
    valid: bool
    models: List[str]
    error: Optional[str] = None
```

### 2. 数据流设计

#### 2.1 模型列表获取流程

```
用户点击"验证连接"
    ↓
前端: EditorTab.tsx
    ↓
调用: POST /api/qwen/validate
    ↓
后端: qwen_router.validate_connection()
    ↓
QwenService.get_available_models()
    ↓
    ├─ 调用 OpenAI Compatible API
    │  └─ 获取大部分模型
    ├─ 补充特殊模型列表
    │  └─ qwen-deep-research, qwq-32b
    └─ 合并、去重、排序
    ↓
返回模型列表
    ↓
前端保存到 Profile.savedModels
    ↓
更新 UI 显示
```

#### 2.2 图像生成流程（可选实现）

```
用户输入提示词 + 选择万相模型
    ↓
前端: DashScopeProvider.generateImage()
    ↓
    ├─ 选项1: 直连 DashScope API (现有方式)
    │  └─ generateDashScopeImage()
    │
    └─ 选项2: 通过后端 API (新增方式)
       └─ POST /api/qwen/image/generate
          ↓
       QwenService.generate_image()
          ↓
       调用 DashScope 图像生成端点
          ↓
       返回图像 URL
```

### 3. 数据模型

#### 3.1 模型元数据

**后端**: `backend/app/services/qwen.py`

```python
MODEL_PRICES = {
    # 图像生成模型（按次计费，非 token 计费）
    "wanx-v1": {"prompt": 0.0, "completion": 0.0},
    "wanx-v2": {"prompt": 0.0, "completion": 0.0},
    "qwen-image-plus": {"prompt": 0.0, "completion": 0.0},
    "wanx-v2.5-image-edit": {"prompt": 0.0, "completion": 0.0},
    "qwen-vl-image-edit": {"prompt": 0.0, "completion": 0.0},
    # ... 其他模型
}

MODEL_CONTEXT_LENGTHS = {
    "wanx-v1": 8192,
    "wanx-v2": 8192,
    "qwen-image-plus": 8192,
    "wanx-v2.5-image-edit": 8192,
    "qwen-vl-image-edit": 8192,
    # ... 其他模型
}
```

**前端**: `frontend/services/providers/tongyi/models.ts`

```typescript
export const TONGYI_MODELS: ModelConfig[] = [
    {
        id: 'wanx-v2',  // 注意：使用 wanx-v2 而非 wanxiang-v2
        name: 'Wanx V2',
        provider: 'tongyi',
        type: 'image-generation',
        contextLength: 8192,
        // ... 其他配置
    },
    // ... 其他模型
];
```

#### 3.2 数据库模型

**Profile.savedModels** (已存在):
```typescript
interface Profile {
    id: string;
    name: string;
    apiKey: string;
    baseUrl?: string;
    savedModels?: string[];  // 保存的模型 ID 列表
    // ... 其他字段
}
```

## 正确性属性

### 1. 模型命名一致性

**属性**: 前后端模型 ID 必须完全一致

**验证方法**:
```python
# 后端测试
def test_model_naming_consistency():
    backend_models = QwenService.MODEL_PRICES.keys()
    frontend_models = load_frontend_models()  # 从 models.ts 加载
    
    assert set(backend_models) == set(frontend_models)
```

### 2. 模型列表完整性

**属性**: 所有万相模型必须被正确获取

**验证方法**:
```python
def test_wanx_models_availability():
    service = QwenService(api_key="test_key")
    models = await service.get_available_models()
    
    required_wanx_models = [
        "wanx-v1", "wanx-v2", "qwen-image-plus",
        "wanx-v2.5-image-edit", "qwen-vl-image-edit"
    ]
    
    for model in required_wanx_models:
        assert model in models
```

### 3. API 端点正确性

**属性**: 万相模型必须使用正确的 API 端点

**验证方法**:
```typescript
// 前端测试
test('wanx-v2 uses correct endpoint', () => {
    const endpoint = resolveDashUrl(baseUrl, 'image-generation', 'wanx-v2');
    expect(endpoint).toContain('/text-to-image/image-synthesis');
});

test('wanx-v1 uses correct endpoint', () => {
    const endpoint = resolveDashUrl(baseUrl, 'image-generation', 'wanx-v1');
    expect(endpoint).toContain('/text2image/image-synthesis');
});
```

## 错误处理

### 1. API 调用失败

**场景**: OpenAI Compatible API 调用失败

**处理策略**:
```python
async def get_available_models(self) -> List[str]:
    all_models = set()
    
    try:
        # 尝试调用 API
        models_response = await self.client.models.list()
        api_models = [model.id for model in models_response.data]
        all_models.update(api_models)
    except Exception as e:
        logger.warning(f"API 调用失败: {str(e)}")
        # 不抛出异常，继续执行
    
    # 补充特殊模型
    all_models.update(SPECIAL_MODELS)
    
    # 降级：返回已知模型列表
    if not all_models:
        logger.warning("所有数据源均失败，使用降级模型列表")
        return sorted(list(self.MODEL_PRICES.keys()))
    
    return sorted(list(all_models))
```

### 2. 模型不存在

**场景**: 用户选择的模型在 API 中不存在

**处理策略**:
```python
async def chat(self, messages, model, **kwargs):
    try:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        return response
    except Exception as e:
        if "model" in str(e).lower() and "not found" in str(e).lower():
            raise ModelNotFoundError(f"模型不存在: {model}", provider="Qwen")
        raise
```

### 3. 前后端命名不一致

**场景**: 前端发送 `wanxiang-v2`，后端期望 `wanx-v2`

**处理策略**:
```python
# 后端路由层添加命名映射
MODEL_NAME_MAPPING = {
    "wanxiang-v2": "wanx-v2",
    "wanxiang-v1": "wanx-v1",
}

def normalize_model_name(model_id: str) -> str:
    """标准化模型名称"""
    return MODEL_NAME_MAPPING.get(model_id, model_id)
```

### 4. CORS 错误

**场景**: 浏览器直连 DashScope API 被 CORS 阻止

**处理策略**:
```typescript
// 前端自动切换到代理
export function resolveDashUrl(baseUrl: string, endpointType: string, modelId?: string): string {
    let root = baseUrl || DEFAULT_DASH_BASE;
    
    // 检测官方域名，自动切换到代理
    if (root.includes('dashscope.aliyuncs.com')) {
        console.debug('[DashScope] 检测到官方 URL，切换到代理:', DEFAULT_DASH_BASE);
        root = DEFAULT_DASH_BASE;
    }
    
    // ... 其他逻辑
}
```

## 性能考虑

### 1. 模型列表缓存

**问题**: 每次验证连接都调用 API，增加延迟

**解决方案**:
```python
class QwenService:
    _model_cache: Optional[List[str]] = None
    _cache_timestamp: Optional[float] = None
    CACHE_TTL = 300  # 5 分钟
    
    async def get_available_models(self) -> List[str]:
        now = time.time()
        
        # 检查缓存
        if (self._model_cache and self._cache_timestamp and 
            now - self._cache_timestamp < self.CACHE_TTL):
            logger.info("[Qwen] 使用缓存的模型列表")
            return self._model_cache
        
        # 获取新数据
        models = await self._fetch_models()
        
        # 更新缓存
        self._model_cache = models
        self._cache_timestamp = now
        
        return models
```

### 2. 并行请求

**问题**: 多个数据源串行获取，增加延迟

**解决方案**:
```python
import asyncio

async def get_available_models(self) -> List[str]:
    # 并行获取多个数据源
    tasks = [
        self._fetch_from_api(),
        self._fetch_special_models(),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_models = set()
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"数据源获取失败: {result}")
        else:
            all_models.update(result)
    
    return sorted(list(all_models))
```

### 3. 图像生成异步处理

**问题**: 图像生成耗时长，阻塞请求

**解决方案**:
```python
# 使用异步任务队列（如 Celery）
@celery_app.task
async def generate_image_task(model_id: str, prompt: str, options: dict):
    service = QwenService(api_key=options['api_key'])
    result = await service.generate_image(model_id, prompt, options)
    return result

# API 端点返回任务 ID
@router.post("/image/generate")
async def generate_image(request: ImageGenRequest):
    task = generate_image_task.delay(
        request.model_id,
        request.prompt,
        request.options
    )
    return {"task_id": task.id}

# 轮询任务状态
@router.get("/image/task/{task_id}")
async def get_task_status(task_id: str):
    task = AsyncResult(task_id)
    if task.ready():
        return {"status": "completed", "result": task.result}
    return {"status": "pending"}
```

## 测试策略

### 1. 单元测试

**后端服务测试**:
```python
# tests/services/test_qwen.py

@pytest.mark.asyncio
async def test_get_available_models():
    """测试模型列表获取"""
    service = QwenService(api_key="test_key")
    models = await service.get_available_models()
    
    # 验证万相模型存在
    assert "wanx-v1" in models
    assert "wanx-v2" in models
    assert "qwen-image-plus" in models

@pytest.mark.asyncio
async def test_model_naming_consistency():
    """测试模型命名一致性"""
    service = QwenService(api_key="test_key")
    models = await service.get_available_models()
    
    # 确保使用 wanx-v2 而非 wanxiang-v2
    assert "wanx-v2" in models
    assert "wanxiang-v2" not in models

@pytest.mark.asyncio
async def test_special_models_included():
    """测试特殊模型被包含"""
    service = QwenService(api_key="test_key")
    models = await service.get_available_models()
    
    assert "qwen-deep-research" in models
    assert "qwq-32b" in models
```

**前端服务测试**:
```typescript
// tests/services/tongyi.test.ts

describe('DashScopeProvider', () => {
    test('should get wanx models', async () => {
        const provider = new DashScopeProvider();
        const models = await provider.getAvailableModels(apiKey, baseUrl);
        
        const wanxModels = models.filter(m => m.id.startsWith('wanx'));
        expect(wanxModels.length).toBeGreaterThan(0);
    });
    
    test('should use correct model names', async () => {
        const provider = new DashScopeProvider();
        const models = await provider.getAvailableModels(apiKey, baseUrl);
        
        const modelIds = models.map(m => m.id);
        expect(modelIds).toContain('wanx-v2');
        expect(modelIds).not.toContain('wanxiang-v2');
    });
});
```

### 2. 集成测试

**API 端点测试**:
```python
# tests/api/test_qwen_routes.py

def test_validate_connection(client):
    """测试连接验证端点"""
    response = client.post("/api/qwen/validate", json={
        "api_key": "test_key",
        "api_url": "https://dashscope.aliyuncs.com"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert len(data["models"]) > 0
    assert "wanx-v2" in data["models"]

def test_get_models(client):
    """测试模型列表端点"""
    response = client.get("/api/qwen/models", headers={
        "Authorization": "Bearer test_key"
    })
    
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    assert len(models) > 0
```

### 3. 端到端测试

**完整流程测试**:
```typescript
// e2e/wanx-model-support.spec.ts

describe('Wanx Model Support E2E', () => {
    test('should validate connection and save models', async () => {
        // 1. 打开配置页面
        await page.goto('/settings');
        
        // 2. 输入 API 密钥
        await page.fill('[data-testid="api-key-input"]', testApiKey);
        
        // 3. 点击验证连接
        await page.click('[data-testid="validate-button"]');
        
        // 4. 等待验证完成
        await page.waitForSelector('[data-testid="validation-success"]');
        
        // 5. 检查模型列表
        const models = await page.$$eval(
            '[data-testid="model-item"]',
            els => els.map(el => el.textContent)
        );
        
        expect(models).toContain('Wanx V2');
        expect(models).toContain('Qwen Image Plus');
    });
    
    test('should generate image with wanx-v2', async () => {
        // 1. 选择 wanx-v2 模型
        await page.selectOption('[data-testid="model-selector"]', 'wanx-v2');
        
        // 2. 输入提示词
        await page.fill('[data-testid="prompt-input"]', 'A beautiful sunset');
        
        // 3. 点击生成
        await page.click('[data-testid="generate-button"]');
        
        // 4. 等待图像生成
        await page.waitForSelector('[data-testid="generated-image"]', {
            timeout: 30000
        });
        
        // 5. 验证图像 URL
        const imageUrl = await page.getAttribute(
            '[data-testid="generated-image"]',
            'src'
        );
        expect(imageUrl).toBeTruthy();
    });
});
```

## 部署考虑

### 1. 环境变量

```bash
# .env
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com
QWEN_SERVICE_ENABLED=true
```

### 2. 配置文件

```yaml
# config/qwen.yaml
qwen:
  enabled: true
  base_url: ${DASHSCOPE_BASE_URL}
  timeout: 60
  max_retries: 3
  cache_ttl: 300
  special_models:
    - qwen-deep-research
    - qwq-32b
```

### 3. 日志配置

```python
# logging.conf
[logger_qwen]
level=INFO
handlers=console,file
qualname=app.services.qwen

[handler_file]
class=FileHandler
level=INFO
formatter=detailed
args=('logs/qwen.log', 'a')
```

## 文档

### 1. API 文档

使用 FastAPI 自动生成的 Swagger 文档：
- `/docs` - Swagger UI
- `/redoc` - ReDoc

### 2. 用户文档

创建 `docs/wanx-model-guide.md`：
- 如何配置通义千问 API 密钥
- 如何验证连接
- 如何使用万相模型生成图像
- 常见问题解答

### 3. 开发者文档

创建 `docs/wanx-model-development.md`：
- 后端服务架构
- API 端点设计
- 数据流说明
- 测试指南

## 下一步

完成设计文档后，将创建任务文档（`tasks.md`），将设计分解为可执行的开发任务。
