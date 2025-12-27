# SSE连接失败调试指南

## 问题描述

**症状**: 前端控制台显示 `[DeepResearchHandler] SSE 连接错误: Event {...}` 和 `[useChat] 执行失败: Error: SSE connection failed`

**影响**: Deep Research功能无法使用，SSE流式响应失败

---

## 根本原因分析

### 1. URL编码不一致（已修复）

**问题位置**: `frontend/hooks/useDeepResearchStream.ts:107-108`

**原问题代码**:
```typescript
const url = `/api/research/stream/${interactionIdRef.current}?last_event_id=${lastEventIdRef.current}&authorization=Bearer%20${import.meta.env.VITE_GEMINI_API_KEY}`;
```

**问题**:
- 手动使用 `Bearer%20` 编码空格，但API Key本身未编码
- 如果API Key包含特殊字符（`+`、`/`、`=`等），会导致Query参数解析失败

**修复方案**:
```typescript
const authParam = encodeURIComponent(`Bearer ${import.meta.env.VITE_GEMINI_API_KEY}`);
const url = `/api/research/stream/${interactionIdRef.current}?last_event_id=${lastEventIdRef.current}&authorization=${authParam}`;
```

### 2. 错误日志不足（已修复）

**问题**: EventSource的 `onerror` 事件不提供详细错误信息，难以定位问题

**修复**:
- 后端增加详细的日志记录（见 `backend/app/routers/research_stream.py:77-138`）
- 前端增强错误捕获和状态监控（见 `frontend/hooks/handlers/DeepResearchHandler.ts:58-130`）

---

## 已实施的修复

### 后端改进 (`backend/app/routers/research_stream.py`)

#### 新增日志点:
1. **请求接收日志**: Line 77
   ```python
   logger.info(f"[SSE] 收到流式请求: interaction_id={interaction_id}, last_event_id={last_event_id}")
   ```

2. **认证验证日志**: Lines 80, 88, 90
   ```python
   logger.error(f"[SSE] 认证失败: authorization={authorization}")
   logger.info(f"[SSE] 认证成功，API Key长度: {len(api_key)}")
   logger.error(f"[SSE] 无法解析authorization参数: {authorization}")
   ```

3. **流式传输日志**: Lines 101, 109, 113, 117
   ```python
   logger.info(f"[SSE] 开始流式传输: interaction_id={interaction_id}")
   logger.debug(f"[SSE] 事件#{event_count}: {event_data.get('event_type')}")
   logger.info(f"[SSE] 流式传输结束: {event_data.get('event_type')}, 共{event_count}个事件")
   logger.warning(f"[SSE] 未收到任何事件: interaction_id={interaction_id}")
   ```

4. **错误详情日志**: Line 120
   ```python
   logger.error(f"[SSE] 流式传输错误: {type(e).__name__}: {str(e)}", exc_info=True)
   ```

#### 改进的错误响应:
```python
error_data = {
    "event_type": "error",
    "error": {
        "type": type(e).__name__,
        "message": str(e)
    }
}
```

### 前端改进 (`frontend/hooks/handlers/DeepResearchHandler.ts`)

#### 新增监控点:
1. **URL构造日志**: Line 51
   ```typescript
   console.log('[DeepResearchHandler] 连接SSE:', sseUrl.replace(apiKey, '***'));
   ```

2. **连接状态监控**: Lines 56, 59-60, 83, 91
   ```typescript
   console.log('[DeepResearchHandler] EventSource readyState:', eventSource.readyState);
   eventSource.onopen = () => {
       console.log('[DeepResearchHandler] ✅ SSE连接已建立');
   };
   ```

3. **事件接收日志**: Line 65
   ```typescript
   console.log('[DeepResearchHandler] 收到事件:', data.event_type);
   ```

4. **详细错误信息**: Lines 100-117
   ```typescript
   console.error('[DeepResearchHandler] ❌ SSE 连接错误:', error);
   console.error('[DeepResearchHandler] EventSource readyState:', eventSource.readyState);
   console.error('[DeepResearchHandler] EventSource url:', eventSource.url);
   // ... 更多错误详情
   ```

---

## 测试步骤

### 1. 启动后端服务

```bash
cd d:\gemini-main\gemini-main
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

**检查点**:
- 后端正常启动在 http://localhost:8000
- 查看控制台确认所有路由已注册

### 2. 启动前端开发服务器

```bash
cd d:\gemini-main\gemini-main
npm run dev
```

**检查点**:
- 前端正常启动在 http://localhost:5173
- Vite代理配置正常 (见 `vite.config.ts:20-40`)

### 3. 测试Deep Research功能

#### 步骤:
1. 打开浏览器开发者工具 (F12)
2. 切换到 **Console** 标签
3. 切换到 **Network** 标签
4. 在应用中选择 "Deep Research Pro Preview (Dec-12-2025)" 模型
5. 输入测试问题并发送

#### 预期日志输出:

**前端控制台**:
```
[DeepResearchHandler] 连接SSE: /api/research/stream/interaction_xxx?authorization=Bearer%20***
[DeepResearchHandler] EventSource readyState: 0
[DeepResearchHandler] ✅ SSE连接已建立
[DeepResearchHandler] 收到事件: interaction.start
[DeepResearchHandler] 收到事件: content.delta
[DeepResearchHandler] 收到事件: content.delta
...
[DeepResearchHandler] ✅ 研究完成
```

**后端日志**:
```
[SSE] 收到流式请求: interaction_id=interaction_xxx, last_event_id=
[SSE] 认证成功，API Key长度: 39
[SSE] 初始化InteractionsService...
[SSE] 开始流式传输: interaction_id=interaction_xxx
[SSE] 事件#1: interaction.start
[SSE] 事件#2: content.delta
...
[SSE] 流式传输结束: interaction.complete, 共15个事件
```

#### 如果出现错误:

**认证失败 (401)**:
```
[SSE] 认证失败: authorization=None
```
或
```
[SSE] 无法解析authorization参数: Bearer
```
**解决**: 检查 `.env` 文件中的 `VITE_GEMINI_API_KEY` 是否正确配置

**流式传输错误**:
```
[SSE] 流式传输错误: ValueError: Invalid interaction_id
```
**解决**: 检查 `/api/research/stream/start` 端点是否成功返回 `interaction_id`

**网络错误**:
```
[DeepResearchHandler] ❌ SSE 连接错误: Event {...}
EventSource readyState: 2 (CLOSED)
```
**解决**:
1. 检查 Network 标签中的请求详情
2. 查看 Response Headers 是否包含 `Content-Type: text/event-stream`
3. 检查后端是否正常运行

---

## EventSource ReadyState 状态码

| 状态码 | 常量名 | 说明 |
|--------|--------|------|
| 0 | CONNECTING | 正在连接 |
| 1 | OPEN | 连接已建立 |
| 2 | CLOSED | 连接已关闭 |

---

## 常见问题排查

### Q1: 前端显示 "SSE connection failed"

**检查清单**:
1. ✅ 后端是否正常运行？
2. ✅ API Key是否正确配置？
3. ✅ 网络请求是否到达后端？（查看Network标签）
4. ✅ 后端日志是否有错误输出？
5. ✅ CORS配置是否正确？（查看 `backend/app/main.py:413-420`）

### Q2: 后端日志显示 "未收到任何事件"

**可能原因**:
- `InteractionsService.stream_interaction()` 未生成任何事件
- Google GenAI SDK 连接失败
- `interaction_id` 无效或不存在

**解决**:
1. 检查 `backend/app/services/interactions_service.py:331-450` 的日志
2. 验证 Google GenAI API 是否可访问
3. 检查 `interaction_id` 是否存在（调用 `/api/interactions/{id}` 端点）

### Q3: 前端显示部分内容后中断

**症状**:
- 收到部分 `content.delta` 事件后连接中断
- 前端显示 "⚠️ 连接中断，以上为部分结果。"

**可能原因**:
- 网络不稳定
- 后端超时
- Google GenAI SDK 流式响应中断

**解决**:
1. 检查后端日志中的错误信息
2. 增加后端超时配置
3. 实现前端重连逻辑（已在 `useDeepResearchStream.ts:152-165` 中实现）

---

## 后续优化建议

### P1: 实现健康检查端点

创建 `/api/research/stream/health` 端点用于检测SSE服务是否正常：

```python
@router.get("/health")
async def sse_health_check():
    return {"status": "ok", "service": "SSE Stream"}
```

### P2: 添加请求速率限制

防止滥用和过载：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/{interaction_id}")
@limiter.limit("10/minute")
async def stream_research_events(...):
    ...
```

### P3: 实现前端断点续传

使用 `last_event_id` 参数实现断点续传（已在 `useDeepResearchStream.ts:107-109` 中部分实现）：

```typescript
const url = `/api/research/stream/${interactionId}?last_event_id=${lastEventId}&authorization=${authParam}`;
```

---

## 文件修改清单

### 已修改的文件:

1. ✅ `backend/app/routers/research_stream.py`
   - 增强日志记录（Lines 74-128）
   - 改进错误处理（Lines 119-128）

2. ✅ `frontend/hooks/handlers/DeepResearchHandler.ts`
   - 增强错误日志（Lines 51-130）
   - 添加连接状态监控（Lines 56-60）
   - 详细错误信息输出（Lines 100-117）

3. ✅ `frontend/hooks/useDeepResearchStream.ts`
   - 修复URL编码问题（Line 108）（注：此文件已弃用，但仍需修复以保持一致性）

### 建议删除的文件:

- `frontend/hooks/useDeepResearchStream.ts` - 已被 DeepResearchHandler 取代，未被使用

---

## 测试用例

### 测试1: 正常流程

**输入**: "请分析人工智能的最新发展趋势"

**预期结果**:
1. 前端显示 "🔍 Deep Research 已启动..."
2. SSE连接成功建立
3. 接收到多个 `content.delta` 事件
4. 最终显示完整的研究报告
5. 连接正常关闭

### 测试2: 认证失败

**模拟**: 删除 `.env` 中的 `VITE_GEMINI_API_KEY`

**预期结果**:
1. 后端日志: `[SSE] 认证失败: authorization=None`
2. 前端收到 401 错误
3. 控制台显示认证相关错误

### 测试3: 无效的interaction_id

**模拟**: 手动构造不存在的 interaction_id

**预期结果**:
1. 后端日志: `[SSE] 流式传输错误: ...`
2. 前端收到 `event_type: "error"` 事件
3. 错误信息包含详细的异常类型和消息

---

**创建日期**: 2025-12-27
**最后更新**: 2025-12-27
**状态**: ✅ 修复已实施，等待测试验证
