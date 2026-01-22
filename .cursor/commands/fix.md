# 修复问题

分析并修复代码中的问题。

## 执行步骤

1. **理解问题**
   - 错误消息是什么
   - 期望行为是什么
   - 实际行为是什么

2. **定位问题**
   - 阅读相关代码
   - 追踪数据流
   - 检查日志和错误

3. **分析根因**
   - 找出问题的根本原因
   - 排除表面现象

4. **实施修复**
   - 最小化更改范围
   - 保持代码风格一致
   - 不引入新问题

5. **验证修复**
   - 确认问题已解决
   - 检查是否有副作用

## 常见问题类型

### 类型错误
```typescript
// 问题：Property 'xxx' does not exist on type 'yyy'
// 修复：添加正确的类型定义或类型守卫
```

### 空值错误
```typescript
// 问题：Cannot read property 'xxx' of undefined
// 修复：添加空值检查
if (data?.property) {
  // 安全使用
}
```

### 异步问题
```typescript
// 问题：状态更新后立即读取得到旧值
// 修复：使用 useEffect 或回调
```

### API 错误
```python
# 问题：API 返回错误
# 修复：检查请求参数、认证、权限
```

### 数据库错误
```python
# 问题：查询返回 None
# 修复：检查查询条件、user_id 过滤
```

## 输出格式

```markdown
## 修复报告

### 问题描述
[原始问题]

### 根因分析
[问题的根本原因]

### 修复方案
[修复思路]

### 代码更改
```diff
- 旧代码
+ 新代码
```

### 验证方法
[如何验证修复成功]
```

## 使用示例

```
/fix TypeError: Cannot read property 'map' of undefined 在 MessageList 组件
```

```
/fix 后端返回 500 错误，日志显示 "API key not found"
```

```
/fix 图片上传后不显示预览
```

```
/fix TypeScript 编译错误：Type 'string' is not assignable to type 'number'
```
