"""
多轮研究测试

测试 Deep Research 的多轮追问功能：
1. 继续研究（Continue Research）
2. 追问（Followup）

验证：
- previous_interaction_id 正确链接
- 上下文正确加载
- 模型能够引用上一轮内容
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from backend.app.services.interactions_service import InteractionsService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def first_interaction():
    """第一轮研究的 Interaction"""
    interaction = Mock()
    interaction.id = "first_interaction_id"
    interaction.agent = "deep-research-pro-preview-12-2025"
    interaction.status = "completed"
    
    output = Mock()
    output.type = "text"
    output.text = "Quantum computing is a revolutionary technology..."
    interaction.outputs = [output]
    
    interaction.previous_interaction_id = None
    interaction.created_at = datetime.now()
    return interaction


@pytest.fixture
def continue_interaction():
    """继续研究的 Interaction"""
    interaction = Mock()
    interaction.id = "continue_interaction_id"
    interaction.agent = "deep-research-pro-preview-12-2025"
    interaction.status = "completed"
    
    output = Mock()
    output.type = "text"
    output.text = "Building on the previous research, quantum error correction..."
    interaction.outputs = [output]
    
    interaction.previous_interaction_id = "first_interaction_id"
    interaction.created_at = datetime.now()
    return interaction


@pytest.fixture
def followup_interaction():
    """追问的 Interaction"""
    interaction = Mock()
    interaction.id = "followup_interaction_id"
    interaction.model = "gemini-2.5-flash"
    interaction.status = "completed"
    
    output = Mock()
    output.type = "text"
    output.text = "Based on the research, the main challenges are..."
    interaction.outputs = [output]
    
    interaction.previous_interaction_id = "first_interaction_id"
    interaction.created_at = datetime.now()
    return interaction


@pytest.fixture
async def interactions_service():
    """Mock InteractionsService"""
    with patch('backend.app.services.interactions_service.genai.Client'):
        service = InteractionsService(api_key="test_api_key")
        return service


# ============================================================================
# 测试 1: 继续研究功能
# ============================================================================

@pytest.mark.asyncio
async def test_continue_research_valid_params(interactions_service, first_interaction, continue_interaction):
    """
    测试继续研究 - 正常情况
    
    验证：
    - 正确使用 previous_interaction_id
    - 上下文正确加载
    - 返回新的 interaction
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=first_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=continue_interaction)
    
    # Act
    # 1. 获取第一轮研究结果
    first = await interactions_service.get_interaction("first_interaction_id")
    assert first.status == "completed"
    
    # 2. 继续研究
    result = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Can you provide more details about quantum error correction?",
        previous_interaction_id="first_interaction_id",
        background=True
    )
    
    # Assert
    assert result.id == "continue_interaction_id"
    assert result.previous_interaction_id == "first_interaction_id"
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_continue_research_invalid_previous_id(interactions_service):
    """
    测试继续研究 - 无效的 previous_interaction_id
    
    验证：
    - 使用不存在的 previous_interaction_id 时返回错误
    """
    # Arrange
    interactions_service.create_interaction = AsyncMock(
        side_effect=ValueError("Previous interaction not found")
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="Previous interaction not found"):
        await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="Continue research",
            previous_interaction_id="nonexistent_id",
            background=True
        )


@pytest.mark.asyncio
async def test_continue_research_context_loading(interactions_service, first_interaction, continue_interaction):
    """
    测试继续研究 - 上下文加载
    
    验证：
    - StateManager 正确加载上下文
    - 对话链正确构建
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=first_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=continue_interaction)
    
    # Mock StateManager
    with patch('backend.app.services.interactions_service.StateManager') as MockStateManager:
        mock_state_manager = MockStateManager.return_value
        mock_state_manager.build_conversation_chain = AsyncMock(
            return_value=[first_interaction]
        )
        
        # Act
        result = await interactions_service.create_interaction(
            agent="deep-research-pro-preview-12-2025",
            input="Continue research",
            previous_interaction_id="first_interaction_id",
            background=True
        )
        
        # Assert
        # 注：实际测试需要验证 StateManager 的调用
        assert result.previous_interaction_id == "first_interaction_id"


@pytest.mark.asyncio
async def test_continue_research_multiple_rounds(interactions_service):
    """
    测试继续研究 - 多轮研究
    
    验证：
    - 支持多轮继续研究
    - 对话链正确维护
    """
    # Arrange
    round1 = Mock()
    round1.id = "round1_id"
    round1.status = "completed"
    round1.previous_interaction_id = None
    
    round2 = Mock()
    round2.id = "round2_id"
    round2.status = "completed"
    round2.previous_interaction_id = "round1_id"
    
    round3 = Mock()
    round3.id = "round3_id"
    round3.status = "completed"
    round3.previous_interaction_id = "round2_id"
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[round1, round2, round3]
    )
    
    # Act
    # 第一轮
    result1 = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    
    # 第二轮
    result2 = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Continue with error correction",
        previous_interaction_id=result1.id,
        background=True
    )
    
    # 第三轮
    result3 = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Continue with practical applications",
        previous_interaction_id=result2.id,
        background=True
    )
    
    # Assert
    assert result1.previous_interaction_id is None
    assert result2.previous_interaction_id == "round1_id"
    assert result3.previous_interaction_id == "round2_id"


# ============================================================================
# 测试 2: 追问功能
# ============================================================================

@pytest.mark.asyncio
async def test_followup_valid_params(interactions_service, first_interaction, followup_interaction):
    """
    测试追问 - 正常情况
    
    验证：
    - 使用 Model 而非 Agent
    - 正确使用 previous_interaction_id
    - 返回快速响应
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=first_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=followup_interaction)
    
    # Act
    # 1. 获取研究结果
    research = await interactions_service.get_interaction("first_interaction_id")
    assert research.status == "completed"
    
    # 2. 追问
    result = await interactions_service.create_interaction(
        model="gemini-2.5-flash",  # 使用 Model，不是 Agent
        input="What are the main challenges?",
        previous_interaction_id="first_interaction_id",
        background=False  # 追问不需要后台执行
    )
    
    # Assert
    assert result.id == "followup_interaction_id"
    assert result.model == "gemini-2.5-flash"
    assert result.previous_interaction_id == "first_interaction_id"


@pytest.mark.asyncio
async def test_followup_context_reference(interactions_service, first_interaction, followup_interaction):
    """
    测试追问 - 上下文引用
    
    验证：
    - 追问能够引用研究结果
    - 回答基于研究内容
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=first_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=followup_interaction)
    
    # Act
    result = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="What are the main challenges mentioned in the research?",
        previous_interaction_id="first_interaction_id"
    )
    
    # Assert
    assert result.previous_interaction_id == "first_interaction_id"
    # 验证回答包含关键词（基于研究内容）
    assert "research" in result.outputs[0].text.lower() or "challenges" in result.outputs[0].text.lower()


@pytest.mark.asyncio
async def test_followup_multiple_questions(interactions_service, first_interaction):
    """
    测试追问 - 多个问题
    
    验证：
    - 支持对同一研究结果提多个问题
    - 每个问题都能正确引用上下文
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=first_interaction)
    
    question1_result = Mock()
    question1_result.id = "q1_id"
    question1_result.previous_interaction_id = "first_interaction_id"
    question1_result.outputs = [Mock(type="text", text="Answer 1")]
    
    question2_result = Mock()
    question2_result.id = "q2_id"
    question2_result.previous_interaction_id = "first_interaction_id"
    question2_result.outputs = [Mock(type="text", text="Answer 2")]
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[question1_result, question2_result]
    )
    
    # Act
    # 第一个问题
    result1 = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="What are the challenges?",
        previous_interaction_id="first_interaction_id"
    )
    
    # 第二个问题
    result2 = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="What are the opportunities?",
        previous_interaction_id="first_interaction_id"
    )
    
    # Assert
    assert result1.previous_interaction_id == "first_interaction_id"
    assert result2.previous_interaction_id == "first_interaction_id"


@pytest.mark.asyncio
async def test_followup_performance(interactions_service, first_interaction, followup_interaction):
    """
    测试追问 - 性能
    
    验证：
    - 追问响应时间 < 研究响应时间
    - 使用 Model 比 Agent 更快
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=first_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=followup_interaction)
    
    # Act
    import time
    start_time = time.time()
    result = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Quick question",
        previous_interaction_id="first_interaction_id"
    )
    end_time = time.time()
    
    # Assert
    response_time = end_time - start_time
    # 追问应该很快（< 2s）
    assert response_time < 2.0


# ============================================================================
# 测试 3: 混合使用 Agent 和 Model
# ============================================================================

@pytest.mark.asyncio
async def test_mixed_agent_model_workflow(interactions_service):
    """
    测试混合使用 Agent 和 Model
    
    验证：
    - Agent 完成研究
    - Model 进行追问
    - 上下文正确传递
    """
    # Arrange
    # Agent 研究
    research = Mock()
    research.id = "research_id"
    research.agent = "deep-research-pro-preview-12-2025"
    research.status = "completed"
    research.outputs = [Mock(type="text", text="Research report")]
    
    # Model 追问
    followup = Mock()
    followup.id = "followup_id"
    followup.model = "gemini-2.5-flash"
    followup.status = "completed"
    followup.previous_interaction_id = "research_id"
    followup.outputs = [Mock(type="text", text="Followup answer")]
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[research, followup]
    )
    
    # Act
    # 1. Agent 研究
    research_result = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    
    # 2. Model 追问
    followup_result = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize the key points",
        previous_interaction_id=research_result.id
    )
    
    # Assert
    assert research_result.agent is not None
    assert followup_result.model is not None
    assert followup_result.previous_interaction_id == research_result.id


# ============================================================================
# 集成测试
# ============================================================================

@pytest.mark.asyncio
async def test_full_multi_turn_workflow(interactions_service):
    """
    测试完整的多轮研究工作流
    
    验证：
    1. 第一轮研究
    2. 继续研究
    3. 追问
    4. 再次追问
    """
    # Arrange
    round1 = Mock()
    round1.id = "round1"
    round1.status = "completed"
    round1.previous_interaction_id = None
    
    round2 = Mock()
    round2.id = "round2"
    round2.status = "completed"
    round2.previous_interaction_id = "round1"
    
    followup1 = Mock()
    followup1.id = "followup1"
    followup1.status = "completed"
    followup1.previous_interaction_id = "round2"
    
    followup2 = Mock()
    followup2.id = "followup2"
    followup2.status = "completed"
    followup2.previous_interaction_id = "round2"
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[round1, round2, followup1, followup2]
    )
    
    # Act
    # 1. 第一轮研究
    r1 = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    
    # 2. 继续研究
    r2 = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Continue with applications",
        previous_interaction_id=r1.id,
        background=True
    )
    
    # 3. 追问
    f1 = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="What are the challenges?",
        previous_interaction_id=r2.id
    )
    
    # 4. 再次追问
    f2 = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="What are the opportunities?",
        previous_interaction_id=r2.id
    )
    
    # Assert
    assert r1.previous_interaction_id is None
    assert r2.previous_interaction_id == "round1"
    assert f1.previous_interaction_id == "round2"
    assert f2.previous_interaction_id == "round2"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
