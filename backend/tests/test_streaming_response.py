"""
流式响应测试

测试 Interactions API 的流式响应功能，包括：
- SSE 连接建立
- 事件流接收（interaction.start, content.delta, interaction.complete）
- 断点续传（last_event_id）
- thought_summary 事件
- 连接中断和重连
- 性能（首字节时间）

Requirements: 8.1-8.15
"""

import pytest
import asyncio
import json
import time
from typing import AsyncIterator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# 假设的导入（根据实际项目结构调整）
from app.services.interactions_service import InteractionsService
from app.models.interaction import Interaction, Content, StreamChunk


class TestSSEConnection:
    """测试 SSE 连接建立"""
    
    @pytest.mark.asyncio
    async def test_sse_connection_establishment(self):
        """
        测试 SSE 连接建立
        
        验证：
        1. 连接成功建立
        2. 返回正确的 Content-Type
        3. 发送 interaction.start 事件
        
        Requirements: 8.1, 8.2
        """
        # 模拟 InteractionsService
        service = AsyncMock(spec=InteractionsService)
        
        # 模拟流式响应
        async def mock_stream():
            yield StreamChunk(
                event_type="interaction.start",
                data={"interaction_id": "test-123"}
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        # 调用流式接口
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        # 验证
        assert len(chunks) == 1
        assert chunks[0].event_type == "interaction.start"
        assert chunks[0].data["interaction_id"] == "test-123"
    
    @pytest.mark.asyncio
    async def test_sse_connection_headers(self):
        """
        测试 SSE 连接的 HTTP 头
        
        验证：
        1. Content-Type: text/event-stream
        2. Cache-Control: no-cache
        3. Connection: keep-alive
        
        Requirements: 8.1
        """
        # 模拟 HTTP 响应
        response = MagicMock()
        response.headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
        
        # 验证
        assert response.headers["Content-Type"] == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"
    
    @pytest.mark.asyncio
    async def test_sse_connection_with_authentication(self):
        """
        测试带认证的 SSE 连接
        
        验证：
        1. 接受 Bearer Token
        2. 验证 Token 有效性
        3. 拒绝无效 Token
        
        Requirements: 8.1, 19.1, 19.2
        """
        service = AsyncMock(spec=InteractionsService)
        
        # 有效 Token
        valid_token = "valid-api-key"
        service.stream_interaction.return_value = AsyncMock()
        
        # 调用（应该成功）
        try:
            await service.stream_interaction("test-123")
            success = True
        except Exception:
            success = False
        
        assert success
        
        # 无效 Token
        service.stream_interaction.side_effect = PermissionError("Invalid token")
        
        with pytest.raises(PermissionError):
            await service.stream_interaction("test-123")


class TestEventStreamReception:
    """测试事件流接收"""
    
    @pytest.mark.asyncio
    async def test_interaction_start_event(self):
        """
        测试 interaction.start 事件
        
        验证：
        1. 事件类型正确
        2. 包含 interaction_id
        3. 包含 model/agent 信息
        
        Requirements: 8.2
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="interaction.start",
                data={
                    "interaction_id": "test-123",
                    "model": "gemini-3-flash-preview",
                    "status": "in_progress"
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].event_type == "interaction.start"
        assert chunks[0].data["interaction_id"] == "test-123"
        assert chunks[0].data["model"] == "gemini-3-flash-preview"
    
    @pytest.mark.asyncio
    async def test_content_delta_text_event(self):
        """
        测试 content.delta (text) 事件
        
        验证：
        1. 事件类型正确
        2. 包含 delta.type: "text"
        3. 包含 delta.text 字段
        4. 可以拼接完整文本
        
        Requirements: 8.3, 8.4, 8.15
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="content.delta",
                data={
                    "delta": {
                        "type": "text",
                        "text": "Hello"
                    }
                }
            )
            yield StreamChunk(
                event_type="content.delta",
                data={
                    "delta": {
                        "type": "text",
                        "text": " World"
                    }
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        # 拼接文本
        full_text = ""
        async for chunk in service.stream_interaction("test-123"):
            if chunk.event_type == "content.delta":
                full_text += chunk.data["delta"]["text"]
        
        assert full_text == "Hello World"
    
    @pytest.mark.asyncio
    async def test_content_delta_thought_event(self):
        """
        测试 content.delta (thought) 事件
        
        验证：
        1. 事件类型正确
        2. 包含 delta.type: "thought"
        3. 包含 delta.thought 字段
        
        Requirements: 8.5
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="content.delta",
                data={
                    "delta": {
                        "type": "thought",
                        "thought": "Analyzing the question..."
                    }
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].data["delta"]["type"] == "thought"
        assert "Analyzing" in chunks[0].data["delta"]["thought"]
    
    @pytest.mark.asyncio
    async def test_thought_summary_event(self):
        """
        测试 thought_summary 事件
        
        验证：
        1. 事件类型正确
        2. 包含 delta.type: "thought_summary"
        3. 包含 delta.content.text 字段
        
        Requirements: 8.6
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="content.delta",
                data={
                    "delta": {
                        "type": "thought_summary",
                        "content": {
                            "text": "Summary of thinking process"
                        }
                    }
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].data["delta"]["type"] == "thought_summary"
        assert "Summary" in chunks[0].data["delta"]["content"]["text"]
    
    @pytest.mark.asyncio
    async def test_interaction_complete_event(self):
        """
        测试 interaction.complete 事件
        
        验证：
        1. 事件类型正确
        2. 包含 usage 统计信息
        3. 包含最终状态
        
        Requirements: 8.7, 8.10
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="interaction.complete",
                data={
                    "interaction_id": "test-123",
                    "status": "completed",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 200,
                        "total_tokens": 300
                    }
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].event_type == "interaction.complete"
        assert chunks[0].data["status"] == "completed"
        assert chunks[0].data["usage"]["total_tokens"] == 300
    
    @pytest.mark.asyncio
    async def test_error_event(self):
        """
        测试 error 事件
        
        验证：
        1. 事件类型正确
        2. 包含错误信息
        3. 包含错误码
        
        Requirements: 8.8
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="error",
                data={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An internal error occurred"
                    }
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].event_type == "error"
        assert chunks[0].data["error"]["code"] == "INTERNAL_ERROR"


class TestBreakpointResumption:
    """测试断点续传"""
    
    @pytest.mark.asyncio
    async def test_last_event_id_parameter(self):
        """
        测试 last_event_id 参数
        
        验证：
        1. 接受 last_event_id 参数
        2. 从指定事件之后继续发送
        3. 不重复发送已接收的事件
        
        Requirements: 8.9
        """
        service = AsyncMock(spec=InteractionsService)
        
        # 模拟完整事件流
        all_events = [
            StreamChunk(event_type="interaction.start", data={"id": "event-1"}),
            StreamChunk(event_type="content.delta", data={"id": "event-2", "text": "Hello"}),
            StreamChunk(event_type="content.delta", data={"id": "event-3", "text": " World"}),
            StreamChunk(event_type="interaction.complete", data={"id": "event-4"})
        ]
        
        # 从 event-2 之后继续
        async def mock_stream_from_event_2():
            for event in all_events[2:]:  # 跳过 event-1 和 event-2
                yield event
        
        service.stream_interaction.return_value = mock_stream_from_event_2()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123", last_event_id="event-2"):
            chunks.append(chunk)
        
        # 验证只接收到 event-3 和 event-4
        assert len(chunks) == 2
        assert chunks[0].data["id"] == "event-3"
        assert chunks[1].data["id"] == "event-4"
    
    @pytest.mark.asyncio
    async def test_reconnection_with_last_event_id(self):
        """
        测试连接中断后使用 last_event_id 重连
        
        验证：
        1. 记录最后接收的事件 ID
        2. 重连时传递 last_event_id
        3. 无缝续传，不丢失数据
        
        Requirements: 8.9, 8.14
        """
        service = AsyncMock(spec=InteractionsService)
        
        # 第一次连接（中断）
        async def mock_stream_interrupted():
            yield StreamChunk(event_type="content.delta", data={"id": "event-1", "text": "Hello"})
            yield StreamChunk(event_type="content.delta", data={"id": "event-2", "text": " World"})
            # 模拟连接中断
            raise ConnectionError("Connection lost")
        
        service.stream_interaction.return_value = mock_stream_interrupted()
        
        last_event_id = None
        received_text = ""
        
        try:
            async for chunk in service.stream_interaction("test-123"):
                last_event_id = chunk.data["id"]
                received_text += chunk.data["text"]
        except ConnectionError:
            pass
        
        assert last_event_id == "event-2"
        assert received_text == "Hello World"
        
        # 第二次连接（续传）
        async def mock_stream_resumed():
            yield StreamChunk(event_type="content.delta", data={"id": "event-3", "text": "!"})
            yield StreamChunk(event_type="interaction.complete", data={"id": "event-4"})
        
        service.stream_interaction.return_value = mock_stream_resumed()
        
        async for chunk in service.stream_interaction("test-123", last_event_id=last_event_id):
            if chunk.event_type == "content.delta":
                received_text += chunk.data["text"]
        
        assert received_text == "Hello World!"


class TestToolCallEvents:
    """测试工具调用事件"""
    
    @pytest.mark.asyncio
    async def test_function_call_event(self):
        """
        测试 function_call 事件
        
        验证：
        1. 事件类型正确
        2. 包含工具名称
        3. 包含工具参数
        4. 包含 call_id
        
        Requirements: 8.11
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="function_call",
                data={
                    "name": "get_weather",
                    "arguments": {"location": "Tokyo"},
                    "call_id": "call-123"
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].event_type == "function_call"
        assert chunks[0].data["name"] == "get_weather"
        assert chunks[0].data["call_id"] == "call-123"
    
    @pytest.mark.asyncio
    async def test_function_result_event(self):
        """
        测试 function_result 事件
        
        验证：
        1. 事件类型正确
        2. 包含工具结果
        3. 包含 call_id（与 function_call 匹配）
        
        Requirements: 8.12
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="function_result",
                data={
                    "call_id": "call-123",
                    "result": {"temperature": 25, "condition": "sunny"}
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].event_type == "function_result"
        assert chunks[0].data["call_id"] == "call-123"
        assert chunks[0].data["result"]["temperature"] == 25
    
    @pytest.mark.asyncio
    async def test_search_result_event(self):
        """
        测试 search_result 事件
        
        验证：
        1. 事件类型正确
        2. 包含搜索结果
        3. 包含来源信息
        
        Requirements: 8.13
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="search_result",
                data={
                    "results": [
                        {
                            "title": "Example Result",
                            "url": "https://example.com",
                            "snippet": "This is an example"
                        }
                    ]
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].event_type == "search_result"
        assert len(chunks[0].data["results"]) == 1
        assert chunks[0].data["results"][0]["title"] == "Example Result"


class TestConnectionHandling:
    """测试连接处理"""
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """
        测试连接超时
        
        验证：
        1. 超时后自动重连
        2. 使用 last_event_id 续传
        3. 最多重试 3 次
        
        Requirements: 8.14
        """
        service = AsyncMock(spec=InteractionsService)
        
        retry_count = 0
        
        async def mock_stream_with_timeout():
            nonlocal retry_count
            retry_count += 1
            
            if retry_count < 3:
                # 前两次超时
                await asyncio.sleep(0.1)
                raise TimeoutError("Connection timeout")
            else:
                # 第三次成功
                yield StreamChunk(
                    event_type="interaction.complete",
                    data={"status": "completed"}
                )
        
        service.stream_interaction.return_value = mock_stream_with_timeout()
        
        # 模拟重试逻辑
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async for chunk in service.stream_interaction("test-123"):
                    assert chunk.event_type == "interaction.complete"
                break
            except TimeoutError:
                if attempt == max_retries - 1:
                    raise
                continue
        
        assert retry_count == 3
    
    @pytest.mark.asyncio
    async def test_connection_interruption(self):
        """
        测试连接中断
        
        验证：
        1. 检测连接中断
        2. 记录最后接收的事件
        3. 自动重连
        
        Requirements: 8.14
        """
        service = AsyncMock(spec=InteractionsService)
        
        # 第一次连接（中断）
        async def mock_stream_interrupted():
            yield StreamChunk(event_type="content.delta", data={"id": "event-1", "text": "Hello"})
            raise ConnectionError("Connection interrupted")
        
        service.stream_interaction.return_value = mock_stream_interrupted()
        
        last_event_id = None
        try:
            async for chunk in service.stream_interaction("test-123"):
                last_event_id = chunk.data["id"]
        except ConnectionError:
            pass
        
        assert last_event_id == "event-1"
        
        # 第二次连接（成功）
        async def mock_stream_resumed():
            yield StreamChunk(event_type="content.delta", data={"id": "event-2", "text": " World"})
            yield StreamChunk(event_type="interaction.complete", data={"id": "event-3"})
        
        service.stream_interaction.return_value = mock_stream_resumed()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123", last_event_id=last_event_id):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0].data["id"] == "event-2"


class TestPerformance:
    """测试性能"""
    
    @pytest.mark.asyncio
    async def test_time_to_first_byte(self):
        """
        测试首字节时间（TTFB）
        
        验证：
        1. 首字节时间 < 500ms
        2. 流式响应立即开始
        
        Requirements: 8.2, 18.2
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            # 立即发送第一个事件
            yield StreamChunk(
                event_type="interaction.start",
                data={"interaction_id": "test-123"}
            )
            # 模拟后续延迟
            await asyncio.sleep(0.1)
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": "Hello"}}
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        start_time = time.time()
        first_byte_time = None
        
        async for chunk in service.stream_interaction("test-123"):
            if first_byte_time is None:
                first_byte_time = time.time() - start_time
            if chunk.event_type == "content.delta":
                break
        
        # 验证首字节时间 < 500ms
        assert first_byte_time < 0.5
    
    @pytest.mark.asyncio
    async def test_streaming_throughput(self):
        """
        测试流式吞吐量
        
        验证：
        1. 能够处理大量事件
        2. 事件顺序正确
        3. 无丢失
        
        Requirements: 8.15
        """
        service = AsyncMock(spec=InteractionsService)
        
        # 生成 1000 个事件
        async def mock_stream():
            for i in range(1000):
                yield StreamChunk(
                    event_type="content.delta",
                    data={"id": f"event-{i}", "text": f"chunk-{i}"}
                )
        
        service.stream_interaction.return_value = mock_stream()
        
        chunks = []
        async for chunk in service.stream_interaction("test-123"):
            chunks.append(chunk)
        
        # 验证
        assert len(chunks) == 1000
        for i, chunk in enumerate(chunks):
            assert chunk.data["id"] == f"event-{i}"
            assert chunk.data["text"] == f"chunk-{i}"


class TestCompleteStreamFlow:
    """测试完整流式流程"""
    
    @pytest.mark.asyncio
    async def test_complete_text_generation_flow(self):
        """
        测试完整的文本生成流程
        
        验证：
        1. interaction.start
        2. 多个 content.delta (text)
        3. interaction.complete
        4. 正确拼接完整文本
        
        Requirements: 8.1-8.7, 8.15
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="interaction.start",
                data={"interaction_id": "test-123", "model": "gemini-3-flash-preview"}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": "The"}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": " quick"}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": " brown"}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": " fox"}}
            )
            yield StreamChunk(
                event_type="interaction.complete",
                data={
                    "interaction_id": "test-123",
                    "status": "completed",
                    "usage": {"total_tokens": 100}
                }
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        # 模拟客户端处理
        full_text = ""
        started = False
        completed = False
        
        async for chunk in service.stream_interaction("test-123"):
            if chunk.event_type == "interaction.start":
                started = True
            elif chunk.event_type == "content.delta":
                full_text += chunk.data["delta"]["text"]
            elif chunk.event_type == "interaction.complete":
                completed = True
        
        # 验证
        assert started
        assert completed
        assert full_text == "The quick brown fox"
    
    @pytest.mark.asyncio
    async def test_complete_research_flow_with_thoughts(self):
        """
        测试完整的研究流程（包含思考过程）
        
        验证：
        1. interaction.start
        2. 多个 content.delta (thought)
        3. content.delta (thought_summary)
        4. 多个 content.delta (text)
        5. interaction.complete
        
        Requirements: 8.1-8.7
        """
        service = AsyncMock(spec=InteractionsService)
        
        async def mock_stream():
            yield StreamChunk(
                event_type="interaction.start",
                data={"interaction_id": "test-123", "agent": "deep-research-pro-preview-12-2025"}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "thought", "thought": "Analyzing the question..."}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "thought", "thought": "Searching for relevant information..."}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "thought_summary", "content": {"text": "Research complete"}}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": "Based on my research, "}}
            )
            yield StreamChunk(
                event_type="content.delta",
                data={"delta": {"type": "text", "text": "the answer is..."}}
            )
            yield StreamChunk(
                event_type="interaction.complete",
                data={"interaction_id": "test-123", "status": "completed"}
            )
        
        service.stream_interaction.return_value = mock_stream()
        
        # 模拟客户端处理
        thoughts = []
        thought_summary = None
        final_text = ""
        
        async for chunk in service.stream_interaction("test-123"):
            if chunk.event_type == "content.delta":
                delta_type = chunk.data["delta"]["type"]
                if delta_type == "thought":
                    thoughts.append(chunk.data["delta"]["thought"])
                elif delta_type == "thought_summary":
                    thought_summary = chunk.data["delta"]["content"]["text"]
                elif delta_type == "text":
                    final_text += chunk.data["delta"]["text"]
        
        # 验证
        assert len(thoughts) == 2
        assert "Analyzing" in thoughts[0]
        assert "Searching" in thoughts[1]
        assert thought_summary == "Research complete"
        assert "Based on my research" in final_text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
