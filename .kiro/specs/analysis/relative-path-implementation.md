# Relative Path Implementation Summary

## 修改概述 (Change Overview)

将上传任务的文件路径从**绝对路径**改为**相对路径**，以实现跨平台兼容性（Windows/Linux）。

## 核心修改 (Core Changes)

### 1. storage.py - 保存相对路径到数据库

**文件**: `backend/app/routers/storage.py`

**修改位置**: 第 495-525 行

**修改内容**:

```python
# Before (旧代码 - 保存绝对路径):
temp_path = os.path.join(TEMP_DIR, f"upload_{task_id}_{file.filename}")
task.source_file_path = temp_path  # 绝对路径：D:\...\backend\temp\upload_xxx.png

# After (新代码 - 保存相对路径):
filename_with_id = f"upload_{task_id}_{file.filename}"

# Absolute path for file system operations
temp_path_abs = os.path.join(TEMP_DIR, filename_with_id)

# Relative path for database storage (cross-platform)
temp_path_rel = os.path.join("backend", "temp", filename_with_id)

# Save file using absolute path
with open(temp_path_abs, 'wb') as f:
    f.write(file_content)

# Store relative path in database
task.source_file_path = temp_path_rel  # 相对路径：backend/temp/upload_xxx.png
```

**关键点**:
- 文件实际保存使用**绝对路径**（`temp_path_abs`）
- 数据库存储使用**相对路径**（`temp_path_rel`）
- 使用 `os.path.join()` 确保跨平台路径分隔符兼容

### 2. upload_worker_pool.py - 读取时转换相对路径

**文件**: `backend/app/services/upload_worker_pool.py`

**修改位置 1**: `_get_file_content` 方法（第 273-297 行）

```python
async def _get_file_content(self, task: UploadTask, worker_name: str) -> bytes:
    """Get file content from local file or URL"""
    if task.source_file_path:
        # Convert relative path to absolute path
        file_path = task.source_file_path
        if not os.path.isabs(file_path):
            # If relative path, convert to absolute based on project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            file_path = os.path.join(project_root, file_path)

        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                return f.read()
        else:
            raise Exception(f"File not found: {file_path}")
    # ...
```

**修改位置 2**: `_handle_success` 方法（第 323-338 行）

```python
# Delete temp file
if task.source_file_path:
    # Convert relative path to absolute path for deletion
    file_path = task.source_file_path
    if not os.path.isabs(file_path):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        file_path = os.path.join(project_root, file_path)

    if os.path.exists(file_path):
        os.remove(file_path)
        log_print(f"[{worker_name}] 🗑️ Temp file deleted: {file_path}")
```

**关键点**:
- 使用 `os.path.isabs()` 判断路径是否为绝对路径
- 相对路径自动转换为绝对路径（基于项目根目录）
- 项目根目录通过 `__file__` 向上 4 级计算得到

## 路径结构 (Path Structure)

### 项目目录结构

```
D:\gemini-main\gemini-main\          # 项目根目录
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   └── storage.py           # __file__ 位置
│   │   └── services/
│   │       └── upload_worker_pool.py # __file__ 位置
│   └── temp/                         # 临时文件目录
│       └── upload_xxx.png            # 临时文件
└── frontend/
```

### 路径计算

**从 storage.py 计算 TEMP_DIR**:

```python
__file__ = "backend/app/routers/storage.py"
os.path.dirname(__file__)                                # backend/app/routers
os.path.dirname(os.path.dirname(__file__))               # backend/app
os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # backend

TEMP_DIR = backend + "/temp" = "backend/temp"  # (绝对路径)
```

**从 upload_worker_pool.py 计算项目根目录**:

```python
__file__ = "backend/app/services/upload_worker_pool.py"
os.path.dirname(__file__)                                # backend/app/services
os.path.dirname(os.path.dirname(__file__))               # backend/app
os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # backend
os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))  # project root

project_root = "D:\gemini-main\gemini-main"  # (绝对路径)
```

## 数据库示例 (Database Example)

### Before (绝对路径)

```
source_file_path: C:\Users\12180\AppData\Local\Temp\upload_xxx.png
```

**问题**:
- Windows 专有路径
- 用户目录硬编码
- 无法跨平台使用
- 无法在不同机器间迁移

### After (相对路径)

```
source_file_path: backend/temp/upload_xxx.png
```

**优点**:
- ✅ 跨平台兼容（Windows/Linux）
- ✅ 不依赖用户目录
- ✅ 可在不同机器间迁移数据库
- ✅ 路径更清晰易读

## 跨平台兼容性 (Cross-Platform Compatibility)

### Windows

```python
# 相对路径（数据库存储）
"backend/temp/upload_xxx.png"

# 转换为绝对路径（文件操作）
"D:\\gemini-main\\gemini-main\\backend\\temp\\upload_xxx.png"
```

### Linux/Mac

```python
# 相对路径（数据库存储）
"backend/temp/upload_xxx.png"

# 转换为绝对路径（文件操作）
"/home/user/gemini-main/backend/temp/upload_xxx.png"
```

**关键**:
- 使用 `os.path.join()` 自动处理路径分隔符（`/` vs `\`）
- 数据库存储统一使用 `/` 分隔符（跨平台标准）
- 文件操作自动转换为平台特定的绝对路径

## 验证步骤 (Verification Steps)

### 1. 清理缓存

```bash
python backend/clear_cache.py
```

### 2. 重启后端

```bash
# Stop current backend (Ctrl+C)
# Restart
pnpm run dev
```

### 3. 前端测试

生成 2 张图片

### 4. 检查数据库

```bash
python backend/check_source_paths.py
```

**预期结果**:

```
Task ID: xxxxxxxx...
  Filename: generated-xxx.png
  Source Path: backend/temp/upload_xxxxxxxx_generated-xxx.png  # 相对路径
  Path Type: RELATIVE
```

### 5. 检查文件

```bash
ls backend/temp/
```

**预期结果**:

```
upload_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx_generated-xxx.png
```

### 6. 验证 Worker 处理

观察日志，应该看到：

```
[worker-0] 📂 Read from local file: D:\gemini-main\gemini-main\backend\temp\upload_xxx.png
[worker-0] 🗑️ Temp file deleted: D:\gemini-main\gemini-main\backend\temp\upload_xxx.png
```

## 注意事项 (Important Notes)

### 1. 项目根目录定位

Worker 池假设从**项目根目录**运行。如果 Uvicorn 从其他目录启动，相对路径转换可能失败。

**确保启动命令从项目根目录运行**:

```bash
# Correct (从项目根目录)
cd D:\gemini-main\gemini-main
pnpm run dev

# Wrong (从 backend 目录)
cd D:\gemini-main\gemini-main\backend
uvicorn app.main:app
```

### 2. 数据库迁移

如果数据库中已有旧任务（绝对路径），需要考虑：
- 清理旧数据：`python backend/clean_upload_tasks.py`
- 或编写迁移脚本转换路径

### 3. 核心问题未解决

**即使实现了相对路径，主要问题仍然存在**：

- ❌ `/api/storage/upload-async` 路由没有被调用
- ❌ 没有 `[UploadAsync]` 日志输出
- ❌ Worker 池从未处理任何任务
- ❌ 数据库记录仍然是系统临时目录的绝对路径

这说明**代码修改没有生效**，需要解决代码加载问题。

## 下一步行动 (Next Steps)

1. **完全重启后端** - 停止所有 Python 进程，重新启动
2. **观察启动日志** - 确认看到 `[Storage Router] TEMP_DIR initialized`
3. **如果仍然失败** - 需要深入排查路由注册和模块导入问题

---

**生成时间**: 2025-12-17 23:35
**状态**: 代码已修改为使用相对路径，等待验证
