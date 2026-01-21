# 日志数据库配置功能说明

> **创建日期**: 2026-01-21  
> **版本**: 1.0

---

## 一、功能概述

在 `backend/app/core/logger.py` 中添加了从数据库读取布尔配置来控制日志显示的功能。

**功能**：
- 从 `SystemConfig` 表的 `enable_logging` 字段读取配置（布尔值）
- 当 `enable_logging = True` 时，显示日志
- 当 `enable_logging = False` 时，不显示日志
- 使用缓存机制（30秒），避免频繁查询数据库

---

## 二、实现细节

### 2.1 数据库模型修改

**文件**：`backend/app/models/db_models.py`

**修改内容**：
- 在 `SystemConfig` 模型中添加 `enable_logging` 字段
- 类型：`Boolean`
- 默认值：`True`（显示日志）
- 位置：第 1409 行

```python
# 日志配置
enable_logging = Column(Boolean, nullable=False, default=True)  # 是否启用日志显示（True=显示，False=不显示）
```

### 2.2 日志过滤器实现

**文件**：`backend/app/core/logger.py`

**新增类**：`DatabaseLoggingFilter`

**功能**：
1. **数据库查询**：从 `SystemConfig` 表读取 `enable_logging` 配置
2. **缓存机制**：缓存30秒，避免频繁查询数据库
3. **线程安全**：使用 `threading.Lock` 确保线程安全
4. **错误处理**：如果数据库查询失败，默认显示日志（向后兼容）

**关键方法**：
- `_get_enable_logging_from_db()`: 从数据库读取配置
- `_get_cached_value()`: 获取缓存的配置值
- `filter()`: 过滤日志记录
- `refresh_cache()`: 手动刷新缓存

### 2.3 集成到日志系统

**修改内容**：
- 在 `setup_logger()` 和 `setup_root_logger()` 中，为所有 handler 添加 `DatabaseLoggingFilter`
- 全局过滤器实例：`_logging_filter`

---

## 三、使用方法

### 3.1 数据库配置

**更新 SystemConfig 表**：
```sql
-- 显示日志
UPDATE system_config SET enable_logging = TRUE WHERE id = 1;

-- 不显示日志
UPDATE system_config SET enable_logging = FALSE WHERE id = 1;
```

**或者通过代码更新**：
```python
from backend.app.core.database import SessionLocal
from backend.app.models.db_models import SystemConfig

db = SessionLocal()
try:
    config = db.query(SystemConfig).filter(SystemConfig.id == 1).first()
    if config:
        config.enable_logging = False  # 或 True
        db.commit()
finally:
    db.close()
```

### 3.2 立即生效（刷新缓存）

**方法 1**：等待缓存过期（30秒后自动刷新）

**方法 2**：手动刷新缓存
```python
from backend.app.core.logger import refresh_logging_config_cache

# 更新数据库配置后，立即刷新缓存
refresh_logging_config_cache()
```

**使用场景**：
- 在系统配置管理界面更新 `enable_logging` 后调用
- 在 API 端点更新配置后调用

---

## 四、技术细节

### 4.1 缓存机制

- **缓存时间**：30秒
- **缓存更新**：自动（缓存过期后）或手动（调用 `refresh_logging_config_cache()`）
- **线程安全**：使用 `threading.Lock` 确保多线程安全

### 4.2 错误处理

- **数据库未初始化**：返回默认值 `True`（显示日志）
- **表不存在**：返回默认值 `True`（显示日志）
- **字段不存在**：返回默认值 `True`（显示日志）
- **查询异常**：返回默认值 `True`（显示日志）

**设计原则**：
- 默认显示日志，确保系统正常运行
- 不记录错误日志，避免循环依赖

### 4.3 性能考虑

- **缓存机制**：减少数据库查询频率（每30秒最多查询1次）
- **延迟加载**：只在需要时查询数据库
- **线程安全**：使用锁确保并发安全

---

## 五、数据库迁移

### 5.1 添加字段

如果数据库已经存在 `SystemConfig` 表，需要添加 `enable_logging` 字段：

```sql
-- PostgreSQL
ALTER TABLE system_config 
ADD COLUMN enable_logging BOOLEAN NOT NULL DEFAULT TRUE;
```

### 5.2 初始化默认值

如果使用代码初始化，`system_config_service.py` 已经包含默认值：

```python
system_config = SystemConfig(
    id=1,
    allow_registration=False,
    max_login_attempts=5,
    max_login_attempts_per_ip=10,
    login_lockout_duration=900,
    enable_logging=True  # 默认启用日志显示
)
```

---

## 六、测试验证

### 6.1 功能测试

1. **测试显示日志**：
   ```python
   # 设置 enable_logging = True
   # 验证日志正常显示
   ```

2. **测试不显示日志**：
   ```python
   # 设置 enable_logging = False
   # 验证日志不显示
   ```

3. **测试缓存刷新**：
   ```python
   # 更新数据库配置
   # 调用 refresh_logging_config_cache()
   # 验证配置立即生效
   ```

### 6.2 性能测试

- 验证缓存机制正常工作
- 验证数据库查询频率合理（每30秒最多1次）

---

## 七、注意事项

1. **数据库连接**：
   - 过滤器在每次日志记录时可能查询数据库（如果缓存过期）
   - 使用独立的数据库会话，避免影响其他操作

2. **缓存时间**：
   - 默认缓存30秒
   - 如果需要立即生效，调用 `refresh_logging_config_cache()`

3. **向后兼容**：
   - 如果数据库查询失败，默认显示日志
   - 确保系统正常运行

4. **线程安全**：
   - 使用 `threading.Lock` 确保多线程安全
   - 缓存更新是原子操作

---

## 八、相关文件

- `backend/app/core/logger.py` - 日志配置和过滤器实现
- `backend/app/models/db_models.py` - SystemConfig 模型定义
- `backend/app/services/common/system_config_service.py` - 系统配置服务

---

## 九、API 参考

### 9.1 refresh_logging_config_cache()

**功能**：刷新日志配置缓存

**使用场景**：
- 在更新 `SystemConfig.enable_logging` 后调用
- 在系统配置管理界面更新后调用

**示例**：
```python
from backend.app.core.logger import refresh_logging_config_cache

# 更新数据库配置
config.enable_logging = False
db.commit()

# 立即刷新缓存，使配置生效
refresh_logging_config_cache()
```

---

## 十、总结

✅ **功能已实现**：
- 从数据库读取 `enable_logging` 配置
- 根据配置控制日志显示
- 使用缓存机制优化性能
- 线程安全
- 向后兼容（默认显示日志）

✅ **数据库模型已更新**：
- `SystemConfig` 模型添加 `enable_logging` 字段
- 默认值：`True`（显示日志）

✅ **服务已更新**：
- `system_config_service.py` 初始化函数包含默认值
