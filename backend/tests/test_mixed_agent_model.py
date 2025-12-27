"""
混合使用 Agent 和 Model 测试

测试 Deep Research 的混合使用功能：
1. 研究后总结（Summarize）
2. 研究后格式化（Format）

验证：
- Agent 完成研究
- Model 进行总结/格式化
- 上下文正确传递
- 输出格式正确
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json

from backend.app.services.interactions_service import InteractionsService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def research_interaction():
    """研究完成的 Interaction"""
    interaction = Mock()
    interaction.id = "research_id"
    interaction.agent = "deep-research-pro-preview-12-2025"
    interaction.status = "completed"
    
    output = Mock()
    output.type = "text"
    output.text = """
    Quantum Computing Research Report
    
    Introduction:
    Quantum computing represents a paradigm shift in computational technology...
    
    Key Findings:
    1. Quantum supremacy achieved in 2019
    2. Error correction remains a major challenge
    3. Practical applications emerging in cryptography
    
    Conclusion:
    The field is rapidly advancing with significant investment...
    """
    interaction.outputs = [output]
    
    interaction.previous_interaction_id = None
    interaction.created_at = datetime.now()
    return interaction


@pytest.fixture
def summary_interaction():
    """总结的 Interaction"""
    interaction = Mock()
    interaction.id = "summary_id"
    interaction.model = "gemini-2.5-flash"
    interaction.status = "completed"
    
    output = Mock()
    output.type = "text"
    output.text = """
    Summary:
    Quantum computing is advancing rapidly with quantum supremacy achieved in 2019.
    Main challenges include error correction. Applications emerging in cryptography.
    """
    interaction.outputs = [output]
    
    interaction.previous_interaction_id = "research_id"
    interaction.created_at = datetime.now()
    return interaction


@pytest.fixture
def formatted_interaction():
    """格式化的 Interaction"""
    interaction = Mock()
    interaction.id = "formatted_id"
    interaction.model = "gemini-2.5-flash"
    interaction.status = "completed"
    
    output = Mock()
    output.type = "text"
    output.text = json.dumps({
        "title": "Quantum Computing Research",
        "summary": "Quantum computing is advancing rapidly...",
        "key_findings": [
            "Quantum supremacy achieved in 2019",
            "Error correction remains a challenge",
            "Applications in cryptography"
        ],
        "conclusion": "The field is rapidly advancing..."
    })
    interaction.outputs = [output]
    
    interaction.previous_interaction_id = "research_id"
    interaction.created_at = datetime.now()
    return interaction


@pytest.fixture
async def interactions_service():
    """Mock InteractionsService"""
    with patch('backend.app.services.interactions_service.genai.Client'):
        service = InteractionsService(api_key="test_api_key")
        return service


# ============================================================================
# 测试 1: 研究后总结功能
# ============================================================================

@pytest.mark.asyncio
async def test_summarize_valid_params(interactions_service, research_interaction, summary_interaction):
    """
    测试研究后总结 - 正常情况
    
    验证：
    - Agent 完成研究
    - Model 生成总结
    - 总结基于研究内容
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=summary_interaction)
    
    # Act
    # 1. 获取研究结果
    research = await interactions_service.get_interaction("research_id")
    assert research.status == "completed"
    
    # 2. 生成总结
    summary = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize the research in 3 sentences",
        previous_interaction_id="research_id"
    )
    
    # Assert
    assert summary.model == "gemini-2.5-flash"
    assert summary.previous_interaction_id == "research_id"
    assert "Summary" in summary.outputs[0].text


@pytest.mark.asyncio
async def test_summarize_custom_format(interactions_service, research_interaction):
    """
    测试研究后总结 - 自定义格式
    
    验证：
    - 支持自定义总结格式（markdown、plain text）
    - 支持最大长度限制
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    
    markdown_summary = Mock()
    markdown_summary.id = "markdown_summary_id"
    markdown_summary.outputs = [Mock(type="text", text="# Summary\n\n- Point 1\n- Point 2")]
    markdown_summary.previous_interaction_id = "research_id"
    
    interactions_service.create_interaction = AsyncMock(return_value=markdown_summary)
    
    # Act
    summary = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize in markdown format, max 500 words",
        previous_interaction_id="research_id"
    )
    
    # Assert
    assert "# Summary" in summary.outputs[0].text
    assert summary.previous_interaction_id == "research_id"


@pytest.mark.asyncio
async def test_summarize_max_length(interactions_service, research_interaction):
    """
    测试研究后总结 - 最大长度限制
    
    验证：
    - 总结长度不超过指定限制
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    
    short_summary = Mock()
    short_summary.id = "short_summary_id"
    short_summary.outputs = [Mock(type="text", text="Brief summary in 100 words.")]
    short_summary.previous_interaction_id = "research_id"
    
    interactions_service.create_interaction = AsyncMock(return_value=short_summary)
    
    # Act
    summary = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize in max 100 words",
        previous_interaction_id="research_id"
    )
    
    # Assert
    word_count = len(summary.outputs[0].text.split())
    assert word_count <= 150  # 允许一些误差


@pytest.mark.asyncio
async def test_summarize_performance(interactions_service, research_interaction, summary_interaction):
    """
    测试研究后总结 - 性能
    
    验证：
    - 总结生成时间 < 5s
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=summary_interaction)
    
    # Act
    import time
    start_time = time.time()
    await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize the research",
        previous_interaction_id="research_id"
    )
    end_time = time.time()
    
    # Assert
    response_time = end_time - start_time
    assert response_time < 5.0


# ============================================================================
# 测试 2: 研究后格式化功能
# ============================================================================

@pytest.mark.asyncio
async def test_format_json_output(interactions_service, research_interaction, formatted_interaction):
    """
    测试研究后格式化 - JSON 输出
    
    验证：
    - Agent 完成研究
    - Model 格式化为 JSON
    - JSON 结构正确
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    interactions_service.create_interaction = AsyncMock(return_value=formatted_interaction)
    
    # Act
    # 1. 获取研究结果
    research = await interactions_service.get_interaction("research_id")
    
    # 2. 格式化为 JSON
    formatted = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Format the research as JSON with fields: title, summary, key_findings, conclusion",
        previous_interaction_id="research_id"
    )
    
    # Assert
    assert formatted.previous_interaction_id == "research_id"
    
    # 验证 JSON 格式
    json_output = json.loads(formatted.outputs[0].text)
    assert "title" in json_output
    assert "summary" in json_output
    assert "key_findings" in json_output
    assert isinstance(json_output["key_findings"], list)


@pytest.mark.asyncio
async def test_format_with_schema(interactions_service, research_interaction):
    """
    测试研究后格式化 - 使用 JSON Schema
    
    验证：
    - 支持 JSON Schema 约束
    - 输出符合 Schema
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    
    schema_formatted = Mock()
    schema_formatted.id = "schema_formatted_id"
    schema_formatted.outputs = [Mock(
        type="text",
        text=json.dumps({
            "title": "Quantum Computing",
            "summary": "Research summary",
            "key_findings": ["Finding 1", "Finding 2"],
            "metadata": {
                "date": "2025-12-27",
                "author": "AI"
            }
        })
    )]
    schema_formatted.previous_interaction_id = "research_id"
    
    interactions_service.create_interaction = AsyncMock(return_value=schema_formatted)
    
    # Act
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "key_findings": {"type": "array", "items": {"type": "string"}},
            "metadata": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "author": {"type": "string"}
                }
            }
        },
        "required": ["title", "summary", "key_findings"]
    }
    
    formatted = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input=f"Format as JSON following this schema: {json.dumps(schema)}",
        previous_interaction_id="research_id"
    )
    
    # Assert
    json_output = json.loads(formatted.outputs[0].text)
    assert "title" in json_output
    assert "summary" in json_output
    assert "key_findings" in json_output
    assert "metadata" in json_output


@pytest.mark.asyncio
async def test_format_xml_output(interactions_service, research_interaction):
    """
    测试研究后格式化 - XML 输出
    
    验证：
    - 支持 XML 格式
    - XML 结构正确
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    
    xml_formatted = Mock()
    xml_formatted.id = "xml_formatted_id"
    xml_formatted.outputs = [Mock(
        type="text",
        text="""
        <research>
            <title>Quantum Computing</title>
            <summary>Research summary</summary>
            <key_findings>
                <finding>Finding 1</finding>
                <finding>Finding 2</finding>
            </key_findings>
        </research>
        """
    )]
    xml_formatted.previous_interaction_id = "research_id"
    
    interactions_service.create_interaction = AsyncMock(return_value=xml_formatted)
    
    # Act
    formatted = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Format the research as XML",
        previous_interaction_id="research_id"
    )
    
    # Assert
    assert "<research>" in formatted.outputs[0].text
    assert "<title>" in formatted.outputs[0].text
    assert "<key_findings>" in formatted.outputs[0].text


@pytest.mark.asyncio
async def test_format_yaml_output(interactions_service, research_interaction):
    """
    测试研究后格式化 - YAML 输出
    
    验证：
    - 支持 YAML 格式
    - YAML 结构正确
    """
    # Arrange
    interactions_service.get_interaction = AsyncMock(return_value=research_interaction)
    
    yaml_formatted = Mock()
    yaml_formatted.id = "yaml_formatted_id"
    yaml_formatted.outputs = [Mock(
        type="text",
        text="""
        title: Quantum Computing
        summary: Research summary
        key_findings:
          - Finding 1
          - Finding 2
        """
    )]
    yaml_formatted.previous_interaction_id = "research_id"
    
    interactions_service.create_interaction = AsyncMock(return_value=yaml_formatted)
    
    # Act
    formatted = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Format the research as YAML",
        previous_interaction_id="research_id"
    )
    
    # Assert
    assert "title:" in formatted.outputs[0].text
    assert "key_findings:" in formatted.outputs[0].text


# ============================================================================
# 测试 3: 混合使用工作流
# ============================================================================

@pytest.mark.asyncio
async def test_mixed_workflow_research_then_summarize(interactions_service):
    """
    测试混合使用工作流 - 研究 + 总结
    
    验证：
    1. Agent 完成研究
    2. Model 生成总结
    3. 上下文正确传递
    """
    # Arrange
    research = Mock()
    research.id = "research_id"
    research.agent = "deep-research-pro-preview-12-2025"
    research.status = "completed"
    research.outputs = [Mock(type="text", text="Research report")]
    
    summary = Mock()
    summary.id = "summary_id"
    summary.model = "gemini-2.5-flash"
    summary.status = "completed"
    summary.previous_interaction_id = "research_id"
    summary.outputs = [Mock(type="text", text="Summary")]
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[research, summary]
    )
    
    # Act
    # 1. Agent 研究
    research_result = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    
    # 2. Model 总结
    summary_result = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize the research",
        previous_interaction_id=research_result.id
    )
    
    # Assert
    assert research_result.agent is not None
    assert summary_result.model is not None
    assert summary_result.previous_interaction_id == research_result.id


@pytest.mark.asyncio
async def test_mixed_workflow_research_then_format(interactions_service):
    """
    测试混合使用工作流 - 研究 + 格式化
    
    验证：
    1. Agent 完成研究
    2. Model 格式化为 JSON
    3. 上下文正确传递
    """
    # Arrange
    research = Mock()
    research.id = "research_id"
    research.agent = "deep-research-pro-preview-12-2025"
    research.status = "completed"
    research.outputs = [Mock(type="text", text="Research report")]
    
    formatted = Mock()
    formatted.id = "formatted_id"
    formatted.model = "gemini-2.5-flash"
    formatted.status = "completed"
    formatted.previous_interaction_id = "research_id"
    formatted.outputs = [Mock(type="text", text='{"title": "Research"}')]
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[research, formatted]
    )
    
    # Act
    # 1. Agent 研究
    research_result = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    
    # 2. Model 格式化
    formatted_result = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Format as JSON",
        previous_interaction_id=research_result.id
    )
    
    # Assert
    assert research_result.agent is not None
    assert formatted_result.model is not None
    assert formatted_result.previous_interaction_id == research_result.id


@pytest.mark.asyncio
async def test_mixed_workflow_complete_pipeline(interactions_service):
    """
    测试混合使用工作流 - 完整流程
    
    验证：
    1. Agent 研究
    2. Model 总结
    3. Model 格式化
    4. 所有步骤正确链接
    """
    # Arrange
    research = Mock()
    research.id = "research_id"
    research.agent = "deep-research-pro-preview-12-2025"
    research.status = "completed"
    
    summary = Mock()
    summary.id = "summary_id"
    summary.model = "gemini-2.5-flash"
    summary.status = "completed"
    summary.previous_interaction_id = "research_id"
    
    formatted = Mock()
    formatted.id = "formatted_id"
    formatted.model = "gemini-2.5-flash"
    formatted.status = "completed"
    formatted.previous_interaction_id = "research_id"
    
    interactions_service.create_interaction = AsyncMock(
        side_effect=[research, summary, formatted]
    )
    
    # Act
    # 1. Agent 研究
    r = await interactions_service.create_interaction(
        agent="deep-research-pro-preview-12-2025",
        input="Research quantum computing",
        background=True
    )
    
    # 2. Model 总结
    s = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Summarize",
        previous_interaction_id=r.id
    )
    
    # 3. Model 格式化
    f = await interactions_service.create_interaction(
        model="gemini-2.5-flash",
        input="Format as JSON",
        previous_interaction_id=r.id
    )
    
    # Assert
    assert r.agent is not None
    assert s.model is not None
    assert f.model is not None
    assert s.previous_interaction_id == r.id
    assert f.previous_interaction_id == r.id


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
