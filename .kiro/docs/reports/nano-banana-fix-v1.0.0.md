# Nano Banana 模型修复报告

## 问题描述

用户报告 "Nano Banana Pro Preview" 模型在 Google provider 的 image-edit 模式下不显示。

## 根本原因

**后端能力推断逻辑缺陷：**

在 `backend/app/services/model_capabilities.py` 的 `get_google_capabilities()` 函数中：

```python
# 旧代码（第 73 行）
if "-image-" in lower_id or "-image" in lower_id:
    # 处理图像模型...
```

**问题：**
- 模型 ID `nano-banana-pro-preview` 不包含 `-image-` 子串
- 因此无法匹配图像模型的模式检查
- 导致该模型被错误地分配为 `vision=False`
- 在 image-edit 模式下，后端过滤器会排除所有 `vision=False` 的模型

## 修复方案

### 1. 后端修复（已完成）

在 `backend/app/services/model_capabilities.py` 中添加了显式的 Nano-Banana 模型检查：

```python
# 新代码（第 68-79 行）
# Nano-Banana models (explicit model IDs without -image- substring)
# Example: nano-banana-pro-preview, nano-banana-pro, nano-banana-preview, nano-banana
if "nano-banana" in lower_id:
    # Nano-Banana Pro: support thinking/reasoning
    if "pro" in lower_id:
        return Capabilities(vision=True, search=True, reasoning=True)
    # Standard Nano-Banana: vision + search only
    return Capabilities(vision=True, search=True)

# Gemini models with -image- substring
if "-image-" in lower_id or "-image" in lower_id:
    # ... 其他图像模型处理
```

**修复效果：**
- `nano-banana-pro-preview` → `vision=True, search=True, reasoning=True`
- `nano-banana-pro` → `vision=True, search=True, reasoning=True`
- `nano-banana-preview` → `vision=True, search=True, reasoning=False`
- `nano-banana` → `vision=True, search=True, reasoning=False`

### 2. 用户操作（必需）

**重要：** 后端修复后，用户需要更新数据库中保存的模型配置。

**步骤：**

1. **打开 Settings 面板**
   - 点击右上角的设置图标

2. **选择 Google Provider 配置**
   - 在 Profiles 标签中，找到你的 Google 配置
   - 点击 Edit 按钮

3. **重新验证连接**
   - 在编辑面板中，点击 "Verify Connection" 按钮
   - 等待后端返回最新的模型列表（使用修复后的逻辑）

4. **保存配置**
   - 确认模型列表中包含 "Nano Banana Pro Preview"
   - 点击 Save 按钮

5. **切换到 Image Edit 模式**
   - 在主界面的模式选择器中，选择 "Image Edit"
   - 在模型下拉菜单中，应该能看到 "Nano Banana Pro Preview"

## 验证测试

运行测试脚本验证修复：

```bash
python backend/test_nano_banana_fix.py
```

**预期输出：**
```
✅ PASS nano-banana-pro-preview
  显示名称: Nano Banana Pro Preview
  vision=True, search=True, reasoning=True
  符合 image-edit 模式: True
```

## 技术细节

### 模型过滤流程

1. **后端能力推断** (`model_capabilities.py`)
   - 根据模型 ID 推断能力（vision, search, reasoning, coding）
   - 返回完整的 `ModelConfig` 对象

2. **后端模式过滤** (`models.py`)
   - 根据 `mode` 参数过滤模型列表
   - image-edit 模式要求：`vision=True` 且不是 veo 模型

3. **前端显示** (`Header.tsx`)
   - 从数据库加载 `savedModels`
   - 根据当前模式应用前端过滤逻辑

### 为什么需要重新验证？

- 数据库中保存的 `savedModels` 包含完整的 `ModelConfig` 对象
- 这些对象在修复前保存，包含错误的 `capabilities.vision=False`
- 重新验证会调用后端 API，使用修复后的逻辑重新生成 `ModelConfig`
- 保存后，数据库中的数据会更新为正确的配置

## 相关文件

- `backend/app/services/model_capabilities.py` - 能力推断逻辑（已修复）
- `backend/app/routers/models.py` - 模型 API 路由（模式过滤）
- `frontend/components/modals/settings/EditorTab.tsx` - 配置编辑器
- `frontend/components/layout/Header.tsx` - 模型选择器
- `backend/test_nano_banana_fix.py` - 验证测试脚本

## 修复版本

- **修复日期：** 2026-01-10
- **修复文件：** `backend/app/services/model_capabilities.py`
- **修复行数：** 第 68-79 行（添加 Nano-Banana 显式检查）
- **测试状态：** ✅ 所有测试通过

## 后续优化建议

### 可选优化 1：Settings 验证时应用模式过滤

**当前行为：**
- Settings 中的 "Verify Connection" 返回所有模型（不考虑模式）
- 用户可能会看到一些在特定模式下不可用的模型

**优化方案：**
- 修改 `UnifiedProviderClient.getAvailableModels()` 添加 `mode` 参数
- 修改 `EditorTab.tsx` 的 `handleVerify()` 传递当前模式
- 这样用户在验证时就只会看到当前模式下可用的模型

**优先级：** 低（当前方案已经可以正常工作）

### 可选优化 2：自动迁移旧配置

**当前行为：**
- 用户需要手动重新验证连接来更新配置

**优化方案：**
- 添加数据库迁移脚本，自动更新所有配置的 `savedModels`
- 在应用启动时检测并更新旧配置

**优先级：** 低（手动更新一次即可，不需要自动化）

---

**修复完成！** 🎉
