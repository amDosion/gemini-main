# Critical Error 问题排查指南

## 问题描述

在浏览器控制台看到错误：
```
Partial failures encountered during init: ['critical_error']
```

## 原因分析

`critical_error` 是在后端初始化服务（`init_service.py`）中，当并行查询数据时出现异常时添加的标记。

### 可能的原因

1. **数据库连接问题**
   - 数据库文件损坏
   - 数据库文件权限问题
   - 数据库连接超时

2. **查询超时**
   - 数据量过大导致查询时间超过 5 秒（`QUERY_TIMEOUT = 5`）
   - 数据库索引缺失导致查询缓慢

3. **数据表结构问题**
   - 数据表不存在
   - 数据表结构不匹配
   - 外键约束问题

4. **并发问题**
   - 多个查询同时访问数据库导致死锁
   - 数据库文件被锁定

## 排查步骤

### 1. 检查后端日志

查看后端控制台输出，查找以下错误信息：
- `[InitService] 并行查询失败`
- `[InitService] 查询超时`
- 具体的异常堆栈信息

### 2. 检查数据库文件

确认数据库文件存在且可访问：
```bash
# Windows
dir backend\*.db

# Linux/Mac
ls -la backend/*.db
```

### 3. 检查数据库连接

运行数据库诊断脚本：
```bash
cd backend
python diagnose_database.py
```

### 4. 检查数据库权限

确保数据库文件有读写权限。

### 5. 检查数据量

如果数据量很大，可能需要：
- 清理旧数据
- 优化数据库索引
- 增加查询超时时间

## 解决方案

### 方案 1：重启后端服务

最简单的方法，有时可以解决临时性的连接问题：

```bash
# 停止当前服务（Ctrl+C）
# 重新启动
npm run dev
```

### 方案 2：清理并重建数据库

**警告**：这会删除所有数据！

```bash
# 备份数据库（可选）
cp backend/app.db backend/app.db.backup

# 删除数据库文件
rm backend/app.db  # Linux/Mac
# 或
del backend\app.db  # Windows

# 重启后端服务，数据库会自动重建
npm run dev
```

### 方案 3：增加查询超时时间

编辑 `backend/app/services/common/init_service.py`：

```python
# 将超时时间从 5 秒增加到 10 秒
QUERY_TIMEOUT = 10
```

### 方案 4：检查并修复数据库

使用 SQLite 工具检查数据库：

```bash
# 使用 sqlite3 命令行工具
sqlite3 backend/app.db

# 检查表结构
.schema

# 检查数据完整性
PRAGMA integrity_check;

# 优化数据库
VACUUM;
```

### 方案 5：查看详细错误日志

在后端代码中添加更详细的日志输出，定位具体是哪个查询失败：

编辑 `backend/app/services/common/init_service.py`，在异常处理部分添加详细日志：

```python
except Exception as e:
    logger.error(f"[InitService] 并行查询失败: {e}", exc_info=True)
    # 添加更详细的错误信息
    import traceback
    logger.error(f"[InitService] 错误堆栈:\n{traceback.format_exc()}")
    result["_metadata"]["partialFailures"].append("critical_error")
```

## 预防措施

1. **定期备份数据库**
2. **监控数据库大小**，及时清理旧数据
3. **优化数据库索引**，提高查询性能
4. **使用连接池**，避免连接问题

## 相关文件

- 初始化服务：`backend/app/services/common/init_service.py`
- 数据库配置：`backend/app/core/database.py`
- 数据库诊断：`backend/diagnose_database.py`

## 如果问题仍然存在

1. 查看完整的后端日志输出
2. 检查浏览器网络请求，查看 `/api/init` 的响应
3. 尝试使用新创建的用户账号登录
4. 检查是否有其他进程占用数据库文件
