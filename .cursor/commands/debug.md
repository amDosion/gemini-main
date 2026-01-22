# 调试问题

分析和修复代码问题、错误和异常。

## 调试流程

### 1. 收集信息

请提供以下信息：
- 错误消息或截图
- 堆栈跟踪（如果有）
- 复现步骤
- 期望行为 vs 实际行为

### 2. 问题分类

#### 前端问题

**React 渲染问题**
```typescript
// 常见原因：无限重渲染
// 检查：useEffect 依赖项
useEffect(() => {
  setData(processData(props.data)); // 每次创建新对象
}, [props.data]);

// 修复：使用 useMemo
const processedData = useMemo(() => processData(props.data), [props.data]);
```

**状态更新问题**
```typescript
// 常见原因：直接修改对象
// 错误：
items.push(newItem);
setItems(items);

// 修复：创建新数组
setItems([...items, newItem]);
```

**类型错误**
```typescript
// 检查：类型定义和实际值是否匹配
// 使用类型守卫
if (isValidMessage(data)) {
  // 现在 data 是正确类型
}
```

#### 后端问题

**认证问题 (401)**
```python
# 检查：
# 1. Token 是否有效
# 2. 是否使用正确的依赖注入
@router.get("/endpoint")
async def endpoint(
    user_id: str = Depends(require_current_user)  # 确保正确
):
    pass
```

**数据库问题**
```python
# 检查：
# 1. user_id 过滤是否正确
# 2. 查询条件是否匹配
result = db.query(Model).filter(
    Model.user_id == user_id,
    Model.id == item_id
).first()

# 调试：打印实际 SQL
print(str(query.statement.compile(compile_kwargs={"literal_binds": True})))
```

**API 调用问题**
```python
# 检查：
# 1. API Key 是否有效
# 2. 请求格式是否正确
# 3. 网络连接

try:
    result = await service.call_api(...)
except Exception as e:
    logger.error(f"API error: {e}")
    # 打印完整错误信息
    import traceback
    traceback.print_exc()
```

#### 网络问题

**CORS 错误**
```
Access to fetch at 'http://...' has been blocked by CORS policy
```
检查：
1. 后端 CORS 配置
2. 请求方法和头是否允许

**连接超时**
```
Error: connect ETIMEDOUT
```
检查：
1. 后端服务是否运行
2. 端口是否正确
3. 防火墙设置

### 3. 调试工具

**前端**
```typescript
// Console 日志
console.log('[DEBUG]', variable);
console.table(array);
console.group('Group Name');

// React DevTools
// 检查组件 props 和 state

// Network 面板
// 检查请求和响应
```

**后端**
```python
# 日志
from app.core.logger import get_logger
logger = get_logger(__name__)
logger.debug(f"[DEBUG] Variable: {variable}")

# 断点调试
import pdb; pdb.set_trace()  # Python debugger

# 打印完整错误
import traceback
traceback.print_exc()
```

## 输出格式

```markdown
## 问题诊断报告

### 问题描述
[错误现象和复现步骤]

### 错误信息
```
[错误消息和堆栈跟踪]
```

### 根因分析
[问题的根本原因]

### 修复方案
[具体的修复代码]

### 验证方法
[如何验证修复是否成功]

### 预防措施
[如何避免类似问题]
```

## 使用示例

```
/debug 前端点击发送按钮后报错：Cannot read property 'map' of undefined
```

```
/debug 后端返回 401 错误，但我已经登录了
```

```
/debug API 调用超时，但直接用 curl 测试正常
```
