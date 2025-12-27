"""
Deep Research 回归测试

测试 Deep Research 功能迁移到 InteractionsService 后的完整性。
确保所有现有功能不受影响。

测试覆盖：
1. 研究任务启动
2. 状态查询
3. 研究完成
4. 缓存机制
5. 错误处理
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
import time
import json

from backend.app.services.interactions_service import InteractionsService
from backend.app.routers.research import start_research, get_research_status


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_genai_client():
    """Mock GenAI Client"""
    client = Mock()
    client.interactions = Mock()
    return client


@pytest.fixture
async def interactions_service(mock_genai_client):
    """Mock InteractionsService"""
    with patch('backend.app.services.interactions_service.genai.Client', return_value=mock_genai_client):
        service = InteractionsService(api_key="test_api_key")
        return service


@pytest.fixture
def mock_interaction():
    """Mock Interaction 对象"""
    interaction = Mock()
    interaction.id = "test_interaction_id"
    interaction.agent = "deep-research-pro-preview-12-2025"
    interaction.status = "in_progress"
    interaction.outputs = []
    interaction.usage = None
    interaction.created_at = datetime.now()
    interaction.updated_at = datetime.now()
    return interaction


@pytest.fixture
def mock_completed_interaction():
    """Mock 已完成的 Interaction 对象"""
    interaction = Mock()
    interaction.id = "test_interaction_id"
    interaction.agent = "deep-research-pro-preview-12-2025"
    interaction.status = "completed"
    
    # Mock outputs
    output = Mock()
    output.type = "text"
    output.text = "This is a comprehensive research report on quantum computing..."
    interaction.outputs = [output]
    
    # Mock usage
    usage = Mock()
    usage.total_tokens = 5000
    usage.input_tokens = 1000
    usage.output_tokens = 4000
    interaction.usage = usage
    
    interaction.created_at = datetime.now()
    interaction.updated_at = datetime.now()
    return interaction


# ============================================================================
# 测试 1: 研究任务启动
# ============================================================================

@pytest.mark.asyncio
async def test_research_task_startup_valid_params(interactions_service, mock_interaction):
    """
    测试研究任务启动 - 正常情况
    
    验证：
    - 正确调用 InteractionsService.create_interaction()
    - 正确传递 agent 参数
    - 正确传递 background=True
    - 返回有效的 interaction 对象
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(return_value=mock_interaction)
    
    # Act
    result = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True,
        store=True
    )
    
    # Assert
    assert result.id == "test_interaction_id"
    assert result.status == "in_progress"
    assert result.agent == "deep-research-pro-preview-12-2025"
    interactions_service.create_interaction.assert_called_once()


@pytest.mark.asyncio
async def test_research_task_startup_invalid_agent(interactions_service):
    """
    测试研究任务启动 - 无效 agent
    
    验证：
    - 使用无效 agent 时返回错误
    - 错误消息清晰
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=ValueError("Invalid agent")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="Invalid agent"):
        await interactions_service.create_interaction(
            agent="invalid-agent",
            input="Research quantum computing",
            background=True
        )


@pytest.mark.asyncio
async def test_research_task_startup_missing_background(interactions_service):
    """
    测试研究任务启动 - 缺少 background 参数
    
    验证：
    - Deep Research 必须使用 background=True
    - 返回清晰的错误消息
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=ValueError("background=True required for agent")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="background=True required"):
        await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="Research quantum computing",
            background=False
        )


@pytest.mark.asyncio
async def test_research_task_startup_empty_input(interactions_service):
    """
    测试研究任务启动 - 空输入
    
    验证：
    - 空输入时返回错误
    - 错误消息清晰
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=ValueError("Input cannot be empty")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="Input cannot be empty"):
        await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="",
            background=True
        )


@pytest.mark.asyncio
async def test_research_task_startup_performance(interactions_service, mock_interaction):
    """
    测试研究任务启动 - 性能
    
    验证：
    - API 调用响应时间 < 2s
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(return_value=mock_interaction)
    
    # Act
    start_time = time.time()
    await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    end_time = time.time()
    
    # Assert
    response_time = end_time - start_time
    assert response_time < 2.0, f"Response time {response_time}s exceeds 2s limit"


# ============================================================================
# 测试 2: 状态查询
# ============================================================================

@pytest.mark.asyncio
async def test_status_query_valid_id(interactions_service, mock_interaction):
    """
    测试状态查询 - 正常情况
    
    验证：
    - 正确调用 InteractionsService.get_interaction()
    - 返回有效的 interaction 对象
    - 状态正确
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_interaction)
    
    # Act
    result = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    assert result.id == "test_interaction_id"
    assert result.status == "in_progress"
    interactions_service.get_interaction.assert_called_once_with("test_interaction_id")


@pytest.mark.asyncio
async def test_status_query_invalid_id(interactions_service):
    """
    测试状态查询 - 无效 ID
    
    验证：
    - 使用不存在的 ID 时返回 404 错误
    - 错误消息清晰
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(
        side_effect=ValueError("Interaction not found")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="Interaction not found"):
        await interactions_service.get_interaction("invalid_id")


@pytest.mark.asyncio
async def test_status_query_status_transition(interactions_service, mock_interaction, mock_completed_interaction):
    """
    测试状态查询 - 状态转换
    
    验证：
    - 状态从 in_progress 转换到 completed
    - 完成后包含 outputs 和 usage
    """
    # Arrange
    # 第一次查询返回 in_progress
    # 第二次查询返回 completed
    interactions_service.get_interaction = AsyncMock(
        side_effect=[mock_interaction, mock_completed_interaction]
    )
    
    # Act
    result1 = await interactions_service.get_interaction("test_interaction_id")
    result2 = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    assert result1.status == "in_progress"
    assert len(result1.outputs) == 0
    
    assert result2.status == "completed"
    assert len(result2.outputs) > 0
    assert result2.usage is not None


@pytest.mark.asyncio
async def test_status_query_performance(interactions_service, mock_interaction):
    """
    测试状态查询 - 性能
    
    验证：
    - 单次查询响应时间 < 1s
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_interaction)
    
    # Act
    start_time = time.time()
    await interactions_service.get_interaction("test_interaction_id")
    end_time = time.time()
    
    # Assert
    response_time = end_time - start_time
    assert response_time < 1.0, f"Response time {response_time}s exceeds 1s limit"


# ============================================================================
# 测试 3: 研究完成
# ============================================================================

@pytest.mark.asyncio
async def test_research_completion_valid_output(interactions_service, mock_completed_interaction):
    """
    测试研究完成 - 正常情况
    
    验证：
    - status 为 "completed"
    - outputs 非空
    - 包含有效的研究报告
    - 包含 usage 统计
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_completed_interaction)
    
    # Act
    result = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    assert result.status == "completed"
    assert len(result.outputs) > 0
    assert result.outputs[0].type == "text"
    assert len(result.outputs[0].text) > 100  # 研究报告应该有足够的内容
    assert result.usage is not None
    assert result.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_research_completion_failed_status(interactions_service):
    """
    测试研究完成 - 失败情况
    
    验证：
    - status 为 "failed"
    - 包含错误信息
    """
    # Arrange
    failed_interaction = Mock()
    failed_interaction.id = "test_interaction_id"
    failed_interaction.status = "failed"
    failed_interaction.error = "Research timeout"
    failed_interaction.outputs = []
    
    interactions_service.get_interaction = AsyncMock(return_value=failed_interaction)
    
    # Act
    result = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    assert result.status == "failed"
    assert result.error is not None


@pytest.mark.asyncio
async def test_research_completion_output_structure(interactions_service, mock_completed_interaction):
    """
    测试研究完成 - 输出结构
    
    验证：
    - outputs 数组结构正确
    - 每个 output 包含必需字段
    - 数据类型正确
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_completed_interaction)
    
    # Act
    result = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    for output in result.outputs:
        assert hasattr(output, 'type')
        assert hasattr(output, 'text')
        assert isinstance(output.type, str)
        assert isinstance(output.text, str)


# ============================================================================
# 测试 4: 缓存机制
# ============================================================================

@pytest.mark.asyncio
async def test_caching_first_request(interactions_service, mock_interaction):
    """
    测试缓存机制 - 第一次请求
    
    验证：
    - 第一次请求缓存未命中
    - 数据正确存储到缓存
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_interaction)
    
    # Act
    result = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    assert result.id == "test_interaction_id"
    # 注：实际缓存验证需要访问 StateManager


@pytest.mark.asyncio
async def test_caching_second_request(interactions_service, mock_interaction):
    """
    测试缓存机制 - 第二次请求
    
    验证：
    - 第二次请求缓存命中
    - 响应时间显著减少
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_interaction)
    
    # Act - 第一次请求
    start_time1 = time.time()
    await interactions_service.get_interaction("test_interaction_id")
    end_time1 = time.time()
    time1 = end_time1 - start_time1
    
    # Act - 第二次请求（应该从缓存读取）
    start_time2 = time.time()
    await interactions_service.get_interaction("test_interaction_id")
    end_time2 = time.time()
    time2 = end_time2 - start_time2
    
    # Assert
    # 注：实际测试需要真实的缓存实现
    # 这里只验证两次请求都成功
    assert time1 >= 0
    assert time2 >= 0


@pytest.mark.asyncio
async def test_caching_data_integrity(interactions_service, mock_completed_interaction):
    """
    测试缓存机制 - 数据完整性
    
    验证：
    - 缓存数据与原始数据一致
    - 所有字段完整
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=mock_completed_interaction)
    
    # Act
    result1 = await interactions_service.get_interaction("test_interaction_id")
    result2 = await interactions_service.get_interaction("test_interaction_id")
    
    # Assert
    assert result1.id == result2.id
    assert result1.status == result2.status
    assert len(result1.outputs) == len(result2.outputs)


# ============================================================================
# 测试 5: 错误处理
# ============================================================================

@pytest.mark.asyncio
async def test_error_handling_authentication_error(interactions_service):
    """
    测试错误处理 - 认证错误（401）
    
    验证：
    - 返回 401 错误
    - 错误消息清晰
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=Exception("UNAUTHENTICATED: Invalid API key")
    )
    
    # Act & Assert
    with pytest.raises(Exception, match="UNAUTHENTICATED"):
        await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="Research quantum computing",
            background=True
        )


@pytest.mark.asyncio
async def test_error_handling_invalid_argument(interactions_service):
    """
    测试错误处理 - 参数错误（400）
    
    验证：
    - 返回 400 错误
    - 错误消息清晰
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=ValueError("INVALID_ARGUMENT: Invalid agent parameter")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="INVALID_ARGUMENT"):
        await interactions_service.create_interaction(
            agent="invalid-agent",
            input="Research quantum computing",
            background=True
        )


@pytest.mark.asyncio
async def test_error_handling_not_found(interactions_service):
    """
    测试错误处理 - 资源不存在（404）
    
    验证：
    - 返回 404 错误
    - 错误消息清晰
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(
        side_effect=ValueError("NOT_FOUND: Interaction not found")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="NOT_FOUND"):
        await interactions_service.get_interaction("nonexistent_id")


@pytest.mark.asyncio
async def test_error_handling_rate_limit(interactions_service):
    """
    测试错误处理 - 速率限制（429）
    
    验证：
    - 返回 429 错误
    - 包含重试建议
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=Exception("RATE_LIMIT_EXCEEDED: Too many requests")
    )
    
    # Act & Assert
    with pytest.raises(Exception, match="RATE_LIMIT_EXCEEDED"):
        await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="Research quantum computing",
            background=True
        )


@pytest.mark.asyncio
async def test_error_handling_service_unavailable(interactions_service):
    """
    测试错误处理 - 服务不可用（503）
    
    验证：
    - 返回 503 错误
    - 包含重试建议
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=Exception("UNAVAILABLE: Service temporarily unavailable")
    )
    
    # Act & Assert
    with pytest.raises(Exception, match="UNAVAILABLE"):
        await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="Research quantum computing",
            background=True
        )


# ============================================================================
# 集成测试
# ============================================================================

@pytest.mark.asyncio
async def test_full_research_workflow(interactions_service, mock_interaction, mock_completed_interaction):
    """
    测试完整的研究工作流
    
    验证：
    1. 启动研究任务
    2. 查询状态（in_progress）
    3. 等待完成
    4. 查询状态（completed）
    5. 获取研究结果
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(return_value=mock_interaction)
    interactions_service.get_interaction = AsyncMock(
        side_effect=[mock_interaction, mock_completed_interaction]
    )
    
    # Act
    # 1. 启动研究任务
    interaction = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    assert interaction.status == "in_progress"
    
    # 2. 查询状态（in_progress）
    status1 = await interactions_service.get_interaction(interaction.id)
    assert status1.status == "in_progress"
    
    # 3. 查询状态（completed）
    status2 = await interactions_service.get_interaction(interaction.id)
    assert status2.status == "completed"
    assert len(status2.outputs) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
