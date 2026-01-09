# Design Document

## Overview

修复两个关键问题：
1. **EditorTab 编辑时无法显示已保存的模型列表** - 用户编辑配置时看不到之前保存的模型
2. **后端 qwen_native.py 中的 ModelConfig 不可哈希错误** - 变量命名误导，导致代码可读性差

## Architecture

### 问题 1: EditorTab 编辑时模型列表丢失

**错误位置**: `frontend/components/modals/settings/EditorTab.tsx:76-79`

**当前代码**:
```typescript
useEffect(() => {
    if (initialData) {
        setFormData({ ...initialData });
        // ✅ 不再依赖 savedModels（后端不返回此字段）
        // 用户需要点击 "Verify Connection" 来获取最新的模型列表
        setVerifiedModels([]);  // ❌ 问题：清空了模型列表！
    }
    // ...
}, [initialData, providerTemplates]);
```

**问题分析**:
1. `formData` 从 `initialData` 加载，包含 `savedModels` ✅
2. 但 `verifiedModels` 被设置为空数组 `[]` ❌
3. UI 渲染使用 `verifiedModels.map()`，所以看不到任何模型
4. 注释说"后端不返回此字段"是错误的 - 后端确实返回 `savedModels`

**根本原因**:
- 开发者误以为后端不返回 `savedModels`
- 实际上后端的 `profiles.py` 和数据库模型都支持 `savedModels` 字段
- 导致编辑时用户必须重新点击 "Verify Connection" 才能看到模型列表

**用户体验问题**:
- 用户编辑配置时，看不到之前保存的模型选择
- 必须重新验证连接才能看到模型列表
- 如果只是修改 API Key 或配置名称，不应该要求重新验证

### 问题 2: 后端变量命名误导

**错误位置**: `backend/app/services/qwen_native.py:713`

**当前代码**:
```python
async def get_available_models(self) -> List[ModelConfig]:
    all_models = set()  # ❌ 变量名暗示存储模型对象
    
    # 数据源1: OpenAI Compatible API
    api_models = [model.id for model in models_response.data]
    all_models.update(api_models)  # 实际添加的是字符串 ID
    
    # 数据源2: 万相图像生成模型
    all_models.update(self.WANX_MODELS)  # 字符串列表
    
    # 数据源3: 特殊模型
    all_models.update(SPECIAL_MODELS)  # 字符串列表
    
    # 构建 ModelConfig
    sorted_models = sorted(list(all_models))
    model_configs = [build_model_config("tongyi", model_id) for model_id in sorted_models]
    return model_configs
```

**问题分析**:
- 变量名 `all_models` 暗示存储的是 `ModelConfig` 对象
- 实际存储的是模型 ID 字符串
- 如果真的尝试添加 `ModelConfig` 对象到 `set()`，会报错：`TypeError: unhashable type: 'ModelConfig'`
- 当前代码能运行，但变量名误导性强

## Components and Interfaces

### 修改 1: EditorTab.tsx

**文件**: `frontend/components/modals/settings/EditorTab.tsx`

**修改位置**: 第 73-103 行的 `useEffect` 钩子

**修改前**:
```typescript
useEffect(() => {
    if (initialData) {
        setFormData({ ...initialData });
        // ✅ 不再依赖 savedModels（后端不返回此字段）
        // 用户需要点击 "Verify Connection" 来获取最新的模型列表
        setVerifiedModels([]);
    } else if (!initialData && providerTemplates.length > 0) {
        // New Profile
        const googleTemplate = providerTemplates.find(p => p.id === 'google');
        setFormData({
            id: uuidv4(),
            name: 'New Configuration',
            providerId: 'google',
            apiKey: '',
            baseUrl: googleTemplate?.baseUrl || '',
            protocol: 'google',
            isProxy: false,
            hiddenModels: [],
            cachedModelCount: 0,
            savedModels: [],
            createdAt: Date.now(),
            updatedAt: Date.now()
        });
        setVerifiedModels([]);
    }
    setVerifyError(null);
}, [initialData, providerTemplates]);
```

**修改后**:
```typescript
useEffect(() => {
    if (initialData) {
        // 编辑现有配置：加载所有数据
        setFormData({ ...initialData });
        
        // ✅ 从 savedModels 加载已保存的模型列表
        // 用户可以看到之前的选择，并在此基础上修改
        setVerifiedModels(initialData.savedModels || []);
        
        console.log('[EditorTab] Loaded existing profile:', {
            id: initialData.id.substring(0, 8) + '...',
            name: initialData.name,
            savedModelsCount: initialData.savedModels?.length || 0,
            timestamp: new Date().toISOString()
        });
    } else if (!initialData && providerTemplates.length > 0) {
        // 创建新配置：初始化空白表单
        const googleTemplate = providerTemplates.find(p => p.id === 'google');
        
        console.log('[EditorTab] Initializing new profile with Google template:', {
            templateFound: !!googleTemplate,
            baseUrl: googleTemplate?.baseUrl,
            timestamp: new Date().toISOString()
        });
        
        setFormData({
            id: uuidv4(),
            name: 'New Configuration',
            providerId: 'google',
            apiKey: '',
            baseUrl: googleTemplate?.baseUrl || '',
            protocol: 'google',
            isProxy: false,
            hiddenModels: [],
            cachedModelCount: 0,
            savedModels: [],
            createdAt: Date.now(),
            updatedAt: Date.now()
        });
        setVerifiedModels([]);
    }
    setVerifyError(null);
}, [initialData, providerTemplates]);
```

**关键变化**:
1. 删除误导性注释："后端不返回此字段"
2. 添加 `setVerifiedModels(initialData.savedModels || [])`
3. 添加调试日志，方便追踪数据加载
4. 保持创建新配置的逻辑不变

### 修改 2: qwen_native.py

**文件**: `backend/app/services/qwen_native.py`

**修改位置**: `get_available_models()` 方法（约第 696-782 行）

**修改前**:
```python
async def get_available_models(self) -> List[ModelConfig]:
    """
    获取可用模型列表（方案3：合并多种数据源）
    """
    SPECIAL_MODELS = [
        "qwen-deep-research",
    ]

    all_models = set()

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=30.0
        )
        models_response = await client.models.list()
        api_models = [model.id for model in models_response.data]
        all_models.update(api_models)
        
        if api_models:
            logger.info(f"[Qwen] OpenAI Compatible API 获取到 {len(api_models)} 个文本模型")
        else:
            logger.warning("[Qwen] OpenAI Compatible API 返回空模型列表")
    except Exception as e:
        logger.warning(f"[Qwen] 获取OpenAI Compatible API模型列表异常: {e}")

    # 数据源2: 万相图像生成模型（静态列表）
    wanx_models_added = [m for m in self.WANX_MODELS if m not in all_models]
    all_models.update(self.WANX_MODELS)
    
    if wanx_models_added:
        logger.info(f"[Qwen] 添加万相图像生成模型: {', '.join(wanx_models_added)}")

    # 数据源3: 补充特殊模型（API未返回的其他模型）
    special_models_added = [m for m in SPECIAL_MODELS if m not in all_models]
    all_models.update(SPECIAL_MODELS)
    
    if special_models_added:
        logger.info(f"[Qwen] 补充特殊模型: {', '.join(special_models_added)}")

    # 去重、排序并构建 ModelConfig
    if all_models:
        sorted_models = sorted(list(all_models))
        model_configs = [build_model_config("tongyi", model_id) for model_id in sorted_models]
        logger.info(f"[Qwen] 最终合并模型列表: {len(model_configs)} 个")
        return model_configs
    else:
        logger.warning("[Qwen] 所有数据源均失败，返回空列表")
        return []
```

**修改后**:
```python
async def get_available_models(self) -> List[ModelConfig]:
    """
    获取可用模型列表（方案3：合并多种数据源）

    数据源优先级：
    1. OpenAI Compatible API（动态获取大部分文本模型）
    2. 万相模型列表（图像生成模型，API不返回）
    3. 特殊模型补充列表（API未返回但实际可用的模型）

    Returns:
        ModelConfig 列表（已去重和排序）
    """
    # 特殊模型补充列表：OpenAI Compatible API 不返回但实际可用的模型
    SPECIAL_MODELS = [
        "qwen-deep-research",  # Deep Research模型（联网搜索功能）
    ]

    # ✅ 使用 set 存储模型 ID 字符串（用于去重）
    all_model_ids = set()

    try:
        from openai import AsyncOpenAI

        # 数据源1: OpenAI兼容API获取模型列表（主要来源 - 文本模型）
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=30.0
        )

        models_response = await client.models.list()

        # 获取所有可用模型 ID
        api_model_ids = [model.id for model in models_response.data]
        all_model_ids.update(api_model_ids)

        if api_model_ids:
            logger.info(f"[Qwen] OpenAI Compatible API 获取到 {len(api_model_ids)} 个文本模型")
        else:
            logger.warning("[Qwen] OpenAI Compatible API 返回空模型列表")

    except Exception as e:
        logger.warning(f"[Qwen] 获取OpenAI Compatible API模型列表异常: {e}")

    # 数据源2: 万相图像生成模型（静态列表）
    wanx_models_added = [m for m in self.WANX_MODELS if m not in all_model_ids]
    all_model_ids.update(self.WANX_MODELS)

    if wanx_models_added:
        logger.info(f"[Qwen] 添加万相图像生成模型: {', '.join(wanx_models_added)}")

    # 数据源3: 补充特殊模型（API未返回的其他模型）
    special_models_added = [m for m in SPECIAL_MODELS if m not in all_model_ids]
    all_model_ids.update(SPECIAL_MODELS)

    if special_models_added:
        logger.info(f"[Qwen] 补充特殊模型: {', '.join(special_models_added)}")

    # 去重、排序并构建 ModelConfig 对象
    if all_model_ids:
        sorted_model_ids = sorted(list(all_model_ids))
        model_configs = [build_model_config("tongyi", model_id) for model_id in sorted_model_ids]
        logger.info(f"[Qwen] 最终合并模型列表: {len(model_configs)} 个")
        return model_configs
    else:
        # 降级：返回空列表
        logger.warning("[Qwen] 所有数据源均失败，返回空列表")
        return []
```

**关键变化**:
1. `all_models` → `all_model_ids`（明确表示存储 ID 字符串）
2. `api_models` → `api_model_ids`
3. `sorted_models` → `sorted_model_ids`
4. 添加详细的文档字符串
5. 添加注释说明数据类型

## Data Models

### ConfigProfile (前端 TypeScript)

```typescript
interface ConfigProfile {
    id: string;
    name: string;
    providerId: string;
    apiKey: string;
    baseUrl: string;
    protocol: string;
    isProxy: boolean;
    hiddenModels: string[];
    cachedModelCount?: number;
    savedModels?: ModelConfig[];  // ✅ 完整的 ModelConfig 对象数组
    createdAt: number;
    updatedAt: number;
}
```

### ModelConfig (前端 TypeScript)

```typescript
interface ModelConfig {
    id: string;
    name: string;
    description: string;
    capabilities: {
        vision: boolean;
        search: boolean;
        reasoning: boolean;
        coding: boolean;
    };
    context_window?: number;
}
```

### DBConfigProfile (后端 Python)

```python
class DBConfigProfile(Base):
    __tablename__ = "config_profiles"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    provider_id = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    protocol = Column(String, nullable=False)
    is_proxy = Column(Boolean, default=False)
    hidden_models = Column(JSON, default=list)
    cached_model_count = Column(Integer, nullable=True)
    saved_models = Column(JSON, default=list)  # ✅ 存储完整的 ModelConfig 对象数组
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do.*

### Property 1: 编辑时模型列表完整性

*For any* 已保存的配置，当用户点击 "Edit" 时，EditorTab 应显示该配置的所有已保存模型，且模型数量应等于 `savedModels.length`。

**Validates: Requirements 2.2, 2.3**

### Property 2: 模型 ID 去重正确性

*For any* 模型 ID 列表（包含重复项），使用 `set()` 去重后，结果列表应不包含重复项，且包含所有唯一的模型 ID。

**Validates: Requirements 4.1**

### Property 3: ModelConfig 构建正确性

*For any* 有效的模型 ID 字符串，`build_model_config("tongyi", model_id)` 应返回一个有效的 `ModelConfig` 对象，其 `id` 字段等于输入的 `model_id`。

**Validates: Requirements 4.2**

### Property 4: 数据持久化完整性

*For any* 保存的 `ConfigProfile`，其 `savedModels` 字段应在数据库中完整存储，并在加载时完整恢复，包含所有字段（id, name, description, capabilities, context_window）。

**Validates: Requirements 3.2, 3.3, 3.4**

## Error Handling

### 错误场景

1. **编辑时 savedModels 为空**: 配置没有保存过模型列表
   - 处理: `verifiedModels` 设置为空数组，用户需要点击 "Verify Connection"

2. **API 调用失败**: OpenAI Compatible API 无法访问
   - 处理: 捕获异常，记录警告，继续使用其他数据源

3. **空模型列表**: 所有数据源均失败
   - 处理: 返回空列表，记录警告

4. **数据库存储失败**: 保存配置时数据库错误
   - 处理: 回滚事务，返回 500 错误

5. **JSON 解析失败**: 加载 `savedModels` 时 JSON 格式错误
   - 处理: 返回空数组，记录警告

## Testing Strategy

### Unit Tests

1. **测试编辑时模型列表加载**
   - 输入: `initialData` 包含 `savedModels: [model1, model2]`
   - 预期: `verifiedModels` 应等于 `[model1, model2]`

2. **测试创建时模型列表初始化**
   - 输入: `initialData` 为 `null`
   - 预期: `verifiedModels` 应为空数组 `[]`

3. **测试模型 ID 去重**
   - 输入: `["qwen-max", "qwen-max", "qwen-plus"]`
   - 预期: `["qwen-max", "qwen-plus"]`（排序后）

4. **测试 ModelConfig 构建**
   - 输入: `"qwen-max"`
   - 预期: `ModelConfig(id="qwen-max", name="Qwen Max", ...)`

### Integration Tests

1. **测试完整创建流程**
   - 操作: 创建新配置 → 验证连接 → 保存
   - 预期: 配置成功保存，包含完整的 `savedModels`

2. **测试完整编辑流程（不重新验证）**
   - 操作: 加载现有配置 → 修改名称 → 保存
   - 预期: 配置成功更新，`savedModels` 保持不变

3. **测试完整编辑流程（重新验证）**
   - 操作: 加载现有配置 → 点击 "Verify Connection" → 保存
   - 预期: 配置成功更新，`savedModels` 更新为最新模型列表

4. **测试前端 API 调用**
   - 请求: `GET /api/providers/templates`
   - 预期: 返回 200，包含 Provider Templates 列表
