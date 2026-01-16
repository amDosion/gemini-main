# 模型过滤系统最终综合分析报告

> 前后端模式过滤规则不一致问题的完整分析

**分析日期**: 2026-01-16  
**状态**: 最终版本

---

## 1. 执行摘要

### 问题概述
前端 `filterModelsByAppMode()` 和后端 `filter_models_by_mode()` 存在 **4 处关键规则不一致**。

### 当前影响
- **直接影响**: 无（前端不传递 mode 参数，后端过滤是死代码）
- **潜在风险**: 高（如果启用后端过滤或新增客户端，将导致模型显示不一致）

### 核心结论
| 模式 | 不一致类型 | 严重程度 |
|------|-----------|---------|
| `image-gen` | 后端缺少 Gemini 图像模型 | 🔴 高 |
| `image-edit` | wanx 排除规则不同 | 🟡 中 |
| `chat` | 后端缺少 imagen/embedding/aqa 排除 | 🟡 中 |
| `pdf-extract` | 后端缺少 embedding/aqa 排除 | 🟡 中 |

---

## 2. 过滤架构说明

### 2.1 三层过滤架构（正确设计）

```
完整模型列表 (从后端获取)
        │
        ▼
┌───────────────────────────────────────┐
│  第一层：模式过滤                      │
│  filterModelsByAppMode()              │
│  职责：根据 appMode 过滤适用的模型      │
│  当前位置：前端 modelFilter.ts         │
│  推荐位置：后端 ModelFilterService     │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  第二层：隐藏模型过滤                  │
│  hiddenModelIds.filter()              │
│  职责：排除用户隐藏的模型              │
│  位置：前端 useModels.ts（保持不变）   │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  第三层：搜索过滤                      │
│  modelSearchQuery.filter()            │
│  职责：用户输入关键词快速搜索模型       │
│  位置：前端 Header.tsx（保持不变）     │
└───────────────────────────────────────┘
        │
        ▼
    最终显示的模型列表
```

### 2.2 各层职责明确

| 过滤层 | 职责 | 当前实现位置 | 推荐实现位置 |
|--------|------|-------------|-------------|
| 模式过滤 | 根据 appMode 过滤模型 | 前端 `modelFilter.ts` | **后端** `ModelFilterService` |
| 隐藏模型 | 排除用户隐藏的模型 | 前端 `useModels.ts` | 前端（保持不变） |
| 搜索过滤 | 用户关键词搜索 | 前端 `Header.tsx` | 前端（保持不变） |

### 2.3 搜索过滤代码（Header.tsx 89-98 行，无问题）

```typescript
// ✅ visibleModels 已经从 useModels hook 返回，已经根据 appMode 过滤过了
// 这里只需要根据搜索查询进一步过滤
const filteredModels = useMemo(() => {
    if (!modelSearchQuery.trim()) return visibleModels;
    
    const query = modelSearchQuery.toLowerCase();
    return visibleModels.filter(m => 
        m.name.toLowerCase().includes(query) || m.id.toLowerCase().includes(query)
    );
}, [visibleModels, modelSearchQuery]);
```

**说明**: 搜索过滤是在模式过滤之后进行的，用于帮助用户快速找到模型，这个逻辑完全正确，不需要修改。

---

## 3. 规则不一致详细对比

### 3.1 `image-gen` 模式 🔴 高优先级

| 规则项 | 前端 | 后端 | 差异 |
|--------|------|------|------|
| 排除 `edit` | ✅ | ✅ | 一致 |
| 包含 `dall` | ✅ | ✅ | 一致 |
| 包含 `wanx` | ✅ | ✅ | 一致 |
| 包含 `flux` | ✅ | ✅ | 一致 |
| 包含 `midjourney` | ✅ | ✅ | 一致 |
| 包含 `-t2i` | ✅ | ✅ | 一致 |
| 包含 `z-image` | ✅ | ✅ | 一致 |
| 包含 `imagen` | ✅ | ✅ | 一致 |
| **Gemini 图像生成** | ✅ | ❌ | **不一致** |

**前端代码** (`modelFilter.ts`):
```typescript
const isGeminiWithImageGen = id.includes('gemini') && 
    (id.includes('image-generation') || id.includes('image-preview') || 
     id.includes('flash-image'));
return isSpecializedImageModel || isGeminiWithImageGen;
```

**后端代码** (`models.py`):
```python
should_include = any(keyword in model_id for keyword in [
    'dall', 'wanx', 'flux', 'midjourney', '-t2i', 'z-image', 'imagen'
])
# ❌ 缺少 Gemini 图像生成模型判断
```

**受影响模型**:
- `gemini-2.0-flash-image-generation`
- `gemini-2.0-flash-image-preview`
- `gemini-2.5-flash-image`

---

### 3.2 `image-edit` 系列模式 🟡 中优先级

| 规则项 | 前端 | 后端 | 差异 |
|--------|------|------|------|
| 需要 vision 能力 | ✅ | ✅ | 一致 |
| 排除 `veo` | ✅ | ✅ | 一致 |
| 排除 `dall` | ✅ | ✅ | 一致 |
| 排除 `flux` | ✅ | ✅ | 一致 |
| 排除 `midjourney` | ✅ | ✅ | 一致 |
| 排除 `z-image-turbo` | ✅ | ✅ | 一致 |
| **排除 wanx** | ✅ 所有 wanx | ❌ 仅 wanx-t2i | **不一致** |

**前端代码** (`modelFilter.ts`):
```typescript
const isTextToImageOnly =
    id.includes('wanx') ||  // ✅ 排除所有 wanx
    id.includes('-t2i') || ...
```

**后端代码** (`models.py`):
```python
is_text_to_image_only = any([
    'wanx' in model_id and '-t2i' in model_id,  # ❌ 仅排除 wanx-t2i
    ...
])
```

**受影响模型**:
- `wanx-v1` (如果存在)
- `wanx-style` (如果存在)
- 其他非 `-t2i` 的 wanx 模型

---

### 3.3 `chat` 模式 🟡 中优先级

| 规则项 | 前端 | 后端 | 差异 |
|--------|------|------|------|
| 排除 `veo` | ✅ | ✅ | 一致 |
| 排除 `tts` | ✅ | ✅ | 一致 |
| 排除 `wanx` | ✅ | ✅ | 一致 |
| 排除 `-t2i` | ✅ | ✅ | 一致 |
| 排除 `z-image` | ✅ | ✅ | 一致 |
| **排除 `imagen`** | ✅ | ❌ | **不一致** |
| **排除 `embedding`** | ✅ | ❌ | **不一致** |
| **排除 `aqa`** | ✅ | ❌ | **不一致** |

**前端代码** (`modelFilter.ts`):
```typescript
const isChatExcluded = id.includes('veo') || id.includes('tts') || 
    id.includes('wanx') || id.includes('-t2i') || id.includes('z-image') ||
    id.includes('imagen') || id.includes('embedding') || id.includes('aqa');
```

**后端代码** (`models.py`):
```python
excluded_keywords = ['veo', 'tts', 'wanx', '-t2i', 'z-image']
# ❌ 缺少 imagen, embedding, aqa
```

**受影响模型**:
- `imagen-3.0-generate-001`
- `text-embedding-004`
- `aqa` (如果存在)

---

### 3.4 `pdf-extract` 模式 🟡 中优先级

| 规则项 | 前端 | 后端 | 差异 |
|--------|------|------|------|
| 排除 `veo` | ✅ | ✅ | 一致 |
| 排除 `tts` | ✅ | ✅ | 一致 |
| 排除 `wanx` | ✅ | ✅ | 一致 |
| 排除 `imagen` | ✅ | ✅ | 一致 |
| 排除 `-t2i` | ✅ | ✅ | 一致 |
| 排除 `z-image` | ✅ | ✅ | 一致 |
| **排除 `embedding`** | ✅ | ❌ | **不一致** |
| **排除 `aqa`** | ✅ | ❌ | **不一致** |

**受影响模型**:
- `text-embedding-004`
- `aqa` (如果存在)

---

## 4. 受影响模型汇总

| 模型 ID | 受影响模式 | 影响程度 |
|---------|-----------|---------|
| `gemini-2.0-flash-image-generation` | image-gen | 🔴 高 |
| `gemini-2.0-flash-image-preview` | image-gen | 🔴 高 |
| `gemini-2.5-flash-image` | image-gen | 🔴 高 |
| `imagen-3.0-generate-001` | chat | 🟡 中 |
| `text-embedding-004` | chat, pdf-extract | 🟡 中 |
| `wanx-*` (非 t2i) | image-edit | 🟡 中 |

---

## 5. 根本原因分析

### 5.1 代码分离维护
- 前端 `modelFilter.ts` 和后端 `models.py` 由不同开发者维护
- 没有共享的规则定义文件

### 5.2 前端先行更新
- 前端添加了 Gemini 图像生成模型支持
- 后端没有同步更新

### 5.3 后端成为死代码
- 前端不传递 `mode` 参数
- 后端过滤逻辑从未被调用
- 没有测试覆盖发现不一致

---

## 6. 推荐解决方案

### 6.1 短期方案：同步后端规则

修改 `backend/app/routers/models/models.py`，使其与前端规则一致。

### 6.2 长期方案：统一后端过滤服务

参考 `docs/MODEL_FILTER_SERVICE_DESIGN.md` 的设计：

1. **创建 `ModelFilterService`**: 集中管理所有过滤规则
2. **声明式规则配置**: 使用 `FilterRule` 数据类定义规则
3. **API 增强**: 后端返回已过滤的模型列表
4. **前端简化**: 删除 `modelFilter.ts`，依赖后端过滤

---

## 7. 实施优先级

### P0 - 立即修复（本周）
- [ ] 后端添加 Gemini 图像生成模型判断

### P1 - 本周修复
- [ ] 后端 chat 模式添加 imagen/embedding/aqa 排除
- [ ] 后端 pdf-extract 模式添加 embedding/aqa 排除

### P2 - 确认后修复
- [ ] 确认 wanx 排除规则的正确性（所有 wanx vs 仅 wanx-t2i）

### P3 - 长期规划
- [ ] 实施统一后端过滤服务设计

---

## 8. 相关文档

- `docs/MODE_FILTER_RULES_INCONSISTENCY.md` - 规则不一致详细分析
- `docs/MODEL_FILTER_SERVICE_DESIGN.md` - 统一过滤服务设计方案
- `docs/MODEL_FILTER_ANALYSIS_V2.md` - 过滤架构分析
