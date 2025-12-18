# Worker Pool 不处理任务问题分析报告（已修复）

## 问题描述

用户上传图片后，任务创建成功但 `/upload-logs` 返回 404，Worker Pool 没有处理任务。

## 🔴 根本原因

后端日志中的关键错误：
```
[WARN] Could not import API routes module: No module named 'routers'
[WARN] API routes not available
```

**原因**：从项目根目录启动后端时，Python 模块路径不正确，导致 API 路由导入失败。

## ✅ 已修复

修改了 `backend/app/main.py`，添加了第三层导入回退，支持从项目根目录启动：

### 修复的导入模块

| 模块 | 原有回退 | 新增回退 |
|------|---------|---------|
| logger/progress_tracker | `.core.logger` → `core.logger` | + `backend.app.core.logger` |
| browser | `.services.browser` → `services.browser` | + `backend.app.services.browser` |
| pdf_extractor | `.services.pdf_extractor` → `services.pdf_extractor` | + `backend.app.services.pdf_extractor` |
| embedding_service | `.services.embedding_service` → `services.embedding_service` | + `backend.app.services.embedding_service` |
| database | `.core.database` → `core.database` | + `backend.app.core.database` |
| API routers | `.routers` → `routers` | + `backend.app.routers` |
| worker_pool | `.services.upload_worker_pool` → `services.upload_worker_pool` | + `backend.app.services.upload_worker_pool` |
| web_search | `.services.browser` → `services.browser` | + `backend.app.services.browser` |

### 导入逻辑示例

```python
# Import API routers
try:
    from .routers import health, storage, ...  # 相对导入
    API_ROUTES_AVAILABLE = True
except ImportError:
    try:
        from routers import health, storage, ...  # 绝对导入（从 backend/app 启动）
        API_ROUTES_AVAILABLE = True
    except ImportError:
        try:
            from backend.app.routers import health, storage, ...  # 从项目根目录启动
            API_ROUTES_AVAILABLE = True
        except ImportError as e:
            logger.warning(f"Could not import API routes module: {e}")
            API_ROUTES_AVAILABLE = False
```

## 验证方法

重启后端后，启动日志应该显示：
```
[INFO] API routes imported via backend.app.routers
[INFO] Worker pool imported via backend.app.services
[INFO] API routes registered (profiles, sessions, personas, storage, image_expand)
```

而不是：
```
[WARN] API routes not available
```

## 支持的启动方式

修复后支持以下启动方式：

1. **从 backend 目录启动**（推荐）：
   ```powershell
   cd D:\gemini-main\gemini-main\backend
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. **从项目根目录启动**（现在也支持）：
   ```powershell
   cd D:\gemini-main\gemini-main
   python -m uvicorn backend.app.main:app --reload --port 8000
   ```

## 修复时间

- 修复日期：2024-12-18
- 修改文件：`backend/app/main.py`
