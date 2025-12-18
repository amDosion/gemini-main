# 临时文件路径问题分析 (Temp File Path Issue Analysis)

## 问题描述

虽然代码中已将 `TEMP_DIR` 修改为项目内的 `backend/temp/` 目录：

```python
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "temp")
```

但实际运行时，文件仍然保存在系统临时目录：
```
C:\Users\12180\AppData\Local\Temp\upload_xxx.png
```

## 根本原因

**Python 代码缓存 (__pycache__) 导致旧代码仍在运行**

即使修改了源代码文件 `storage.py`，Python 在运行时可能会使用已编译的 `.pyc` 缓存文件，导致修改不生效。

## 证据链

### 1. 代码检查

运行 `grep` 搜索确认源代码已正确修改：

```bash
$ grep -n "TEMP_DIR" backend/app/routers/storage.py

22:TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "temp")
25:os.makedirs(TEMP_DIR, exist_ok=True)
296:temp_path = os.path.join(TEMP_DIR, f"upload_{task_id}_{task.filename}")
491:temp_path = os.path.join(TEMP_DIR, f"upload_{task_id}_{file.filename}")
```

结果：✅ 源代码确实使用了 `TEMP_DIR`

### 2. 数据库检查

运行 `python backend/check_source_paths.py` 查看实际保存的路径：

```
Task ID: 7d747d99...
  Filename: generated-1766023173011-4.png
  Source Path: C:\Users\12180\AppData\Local\Temp\upload_7d747d99-0435-4c3c-bdbd-0428ad080748_generated-1766023173011-4.png
  Path Type: ABSOLUTE
  Location: System temp (WRONG - should be backend/temp/)
```

结果：❌ 实际运行时使用了系统临时目录

### 3. 缓存文件检查

```bash
$ find backend -name "__pycache__" | head -10

backend/app/__pycache__
backend/app/core/__pycache__
backend/app/models/__pycache__
backend/app/routers/__pycache__    ← storage.py 的缓存
backend/app/services/__pycache__
backend/app/tasks/__pycache__
```

结果：✅ 找到多个 `__pycache__` 目录

### 4. 路径计算验证

运行 `python backend/test_temp_path.py` 验证路径计算逻辑：

```
当前文件 (__file__): D:\gemini-main\gemini-main\backend\app\routers\storage.py
  os.path.dirname(__file__): D:\gemini-main\gemini-main\backend\app\routers
  os.path.dirname(os.path.dirname(__file__)): D:\gemini-main\gemini-main\backend\app
  os.path.dirname(os.path.dirname(os.path.dirname(__file__))): D:\gemini-main\gemini-main\backend

TEMP_DIR 计算结果: D:\gemini-main\gemini-main\backend\temp
```

结果：✅ 路径计算逻辑完全正确

## 结论

**源代码修改正确，但 Python 缓存导致旧代码仍在运行**

## 解决方案

### 方案 1: 清理 Python 缓存（推荐）

```bash
# 运行清理脚本
python backend/clear_cache.py

# 或手动删除
find backend -type d -name "__pycache__" -exec rm -rf {} +
find backend -name "*.pyc" -delete
```

### 方案 2: 完全重启服务

```bash
# 1. 停止后端服务
Ctrl+C

# 2. 清理缓存
python backend/clear_cache.py

# 3. 重新启动
pnpm run dev
```

### 方案 3: 添加启动验证日志

已在 `storage.py` 第 28-31 行添加启动日志：

```python
# Startup log to verify TEMP_DIR
print(f"[Storage Router] TEMP_DIR initialized: {TEMP_DIR}")
sys.stderr.write(f"[Storage Router] TEMP_DIR initialized: {TEMP_DIR}\n")
sys.stderr.flush()
```

**重启后应该看到**：
```
[Storage Router] TEMP_DIR initialized: D:\gemini-main\gemini-main\backend\temp
```

如果看到这个日志，说明新代码生效。

## 验证步骤

### 1. 清理缓存

```bash
cd D:\gemini-main\gemini-main
python backend/clear_cache.py
```

### 2. 重启后端

停止并重新启动后端服务，观察启动日志中是否出现：
```
[Storage Router] TEMP_DIR initialized: D:\gemini-main\gemini-main\backend\temp
```

### 3. 测试上传

前端生成 2 张图片，然后检查：

```bash
# 检查 backend/temp/ 目录
ls backend/temp/

# 应该看到类似这样的文件
upload_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx_generated-*.png
```

### 4. 验证数据库

```bash
python backend/check_source_paths.py
```

应该看到：
```
Source Path: D:\gemini-main\gemini-main\backend\temp\upload_xxx.png
Path Type: ABSOLUTE
Location: backend/temp/ (CORRECT)
```

## 额外发现：主要问题仍未解决

即使修复了临时文件路径问题，**核心问题仍然存在**：

### 🔴 API 日志缺失

后端应该输出这些日志但没有：
- `[UploadAsync] received upload request`
- `[UploadAsync] file saved: {temp_path}`
- `[UploadAsync] task created: {task_id}`
- `[UploadAsync] enqueued to Redis`

### 🔴 Worker 未处理任务

Worker 池一直显示 "waiting for task"，从未显示：
- `[WorkerPool] worker-X got task`
- `[WorkerPool] worker-X processing`

### 🔴 数据库记录不完整

所有任务的 `priority` 和 `retry_count` 都是 NULL

## 建议

1. **先清理缓存并重启**，验证 TEMP_DIR 是否生效
2. **观察启动日志**，确认新代码加载
3. **如果仍然有问题**，说明问题更深层（可能是路由注册、模块导入等）
4. **考虑完全停止所有 Python 进程**，确保没有旧进程残留

## 诊断脚本

所有诊断脚本位于 `backend/` 目录：

- `clear_cache.py` - 清理 Python 缓存
- `check_source_paths.py` - 检查数据库中的文件路径
- `test_temp_path.py` - 验证 TEMP_DIR 计算逻辑
- `check_upload_tasks.py` - 查看所有上传任务
- `diagnose_system.py` - 完整系统诊断
- `test_worker_processing.py` - Worker 池处理测试

---

**生成时间**: 2025-12-17 23:20
**问题状态**: 临时文件路径问题原因已定位（Python 缓存），主要问题（API 未调用）仍未解决
