# backend/tests/integration/test_research_e2e.py

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

import pytest
from httpx import AsyncClient

from app.main import app
from app.utils.rate_limiter import RateLimiter
from app.utils.research_cache import ResearchCache
from app.utils.prompt_security_validator import PromptSecurityValidator
from app.dependencies import get_rate_limiter, get_cache, get_validator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_rate_limiter():
    """Mock RateLimiter 依赖"""
    limiter = MagicMock(spec=RateLimiter)
    limiter.check_rate_limit = AsyncMock(return_value=True)
    return limiter


@pytest.fixture
def mock_cache():
    """Mock ResearchCache 依赖"""
    cache = MagicMock(spec=ResearchCache)
    cache.get_cached_result = MagicMock(return_value=None)
    cache.get_cached_interaction = MagicMock(return_value=None)
    cache.cache_interaction = MagicMock()
    cache.cache_research_result = MagicMock()
    cache.delete_cached_interaction = MagicMock()
    return cache


@pytest.fixture
def mock_validator():
    """Mock PromptSecurityValidator 依赖"""
    validator = MagicMock(spec=PromptSecurityValidator)
    validator.validate_prompt = MagicMock(return_value=(True, []))
    return validator


@pytest.fixture
async def test_client(mock_rate_limiter, mock_cache, mock_validator):
    """创建测试客户端并覆盖依赖"""
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate_limiter
    app.dependency_overrides[get_cache] = lambda: mock_cache
    app.dependency_overrides[get_validator] = lambda: mock_validator
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    # 清理依赖覆盖
    app.dependency_overrides.clear()


@pytest.fixture
def mock_genai_client():
    """Mock google.genai.Client"""
    with patch('app.routers.research.genai') as mock_genai:
        # 创建 mock client
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        # 创建 mock interaction
        mock_interaction = MagicMock()
        mock_interaction.id = str(uuid.uuid4())
        mock_interaction.status = "in_progress"
        mock_interaction.outputs = []
        mock_interaction.usage = None
        
        # 配置 interactions API
        mock_client.interactions.create.return_value = mock_interaction
        mock_client.interactions.get.return_value = mock_interaction
        mock_client.interactions.delete.return_value = None
        
        yield mock_client, mock_interaction


# ============================================================================
# Test Cases
# ============================================================================

class TestResearchE2E:
    """端到端深度研究代理集成测试"""
    
    @pytest.mark.asyncio
    async def test_successful_research_workflow(
        self,
        test_client: AsyncClient,
        mock_genai_client,
        mock_cache
    ):
        """测试成功的完整研究工作流：启动 → 轮询 → 获取结果"""
        mock_client, mock_interaction = mock_genai_client
        
        # 1. 启动研究任务
        start_response = await test_client.post(
            "/api/research/start",
            json={"prompt": "测试查询：什么是 FastAPI？"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert start_response.status_code == 200
        start_data = start_response.json()
        assert "interaction_id" in start_data
        assert start_data["status"] == "in_progress"
        assert start_data["cached"] is False
        
        interaction_id = start_data["interaction_id"]
        
        # 验证 Gemini API 被调用
        mock_client.interactions.create.assert_called_once()
        
        # 2. 轮询任务状态（进行中）
        status_response = await test_client.get(
            f"/api/research/status/{interaction_id}",
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "in_progress"
        
        # 3. 模拟任务完成
        mock_interaction.status = "completed"
        mock_output = MagicMock()
        mock_output.type = "text"
        mock_output.text = "这是研究结果报告。"
        mock_interaction.outputs = [mock_output]
        
        # 4. 获取完成状态
        completed_response = await test_client.get(
            f"/api/research/status/{interaction_id}",
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert completed_response.status_code == 200
        completed_data = completed_response.json()
        assert completed_data["status"] == "completed"
        assert completed_data["result"] == "这是研究结果报告。"
        
        # 验证结果被缓存
        mock_cache.cache_interaction.assert_called()
        mock_cache.cache_research_result.assert_called()
    
    @pytest.mark.asyncio
    async def test_cached_result(
        self,
        test_client: AsyncClient,
        mock_genai_client,
        mock_cache
    ):
        """测试缓存命中场景"""
        # 配置缓存返回结果
        cached_interaction_id = str(uuid.uuid4())
        mock_cache.get_cached_result.return_value = {
            'interaction_id': cached_interaction_id,
            'result': '缓存的研究结果'
        }
        
        # 启动研究任务
        response = await test_client.post(
            "/api/research/start",
            json={"prompt": "测试查询"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True
        assert data["status"] == "completed"
        assert data["interaction_id"] == cached_interaction_id
        
        # 验证没有调用 Gemini API
        mock_genai_client[0].interactions.create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_task_cancellation(
        self,
        test_client: AsyncClient,
        mock_genai_client,
        mock_cache
    ):
        """测试任务取消功能"""
        mock_client, mock_interaction = mock_genai_client
        
        # 1. 启动任务
        start_response = await test_client.post(
            "/api/research/start",
            json={"prompt": "一个将被取消的查询"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert start_response.status_code == 200
        interaction_id = start_response.json()["interaction_id"]
        
        # 2. 取消任务
        cancel_response = await test_client.post(
            f"/api/research/cancel/{interaction_id}",
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert cancel_response.status_code == 200
        assert "cancelled" in cancel_response.json()["message"].lower()
        
        # 验证 API 调用
        mock_client.interactions.delete.assert_called_once_with(interaction_id)
        mock_cache.delete_cached_interaction.assert_called_once_with(interaction_id)
    
    @pytest.mark.asyncio
    async def test_error_handling(
        self,
        test_client: AsyncClient,
        mock_genai_client
    ):
        """测试错误处理"""
        mock_client, _ = mock_genai_client
        
        # 配置 API 抛出异常
        mock_client.interactions.create.side_effect = Exception("API Error")
        
        # 启动任务
        response = await test_client.post(
            "/api/research/start",
            json={"prompt": "测试错误处理"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        # 验证错误响应
        assert response.status_code >= 400
        data = response.json()
        assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(
        self,
        test_client: AsyncClient,
        mock_rate_limiter
    ):
        """测试速率限制"""
        # 配置速率限制器返回 False
        mock_rate_limiter.check_rate_limit.return_value = False
        
        response = await test_client.post(
            "/api/research/start",
            json={"prompt": "测试速率限制"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"] == "RATE_LIMIT_EXCEEDED"
    
    @pytest.mark.asyncio
    async def test_invalid_prompt(
        self,
        test_client: AsyncClient,
        mock_validator
    ):
        """测试不安全的 prompt"""
        # 配置验证器返回不安全
        mock_validator.validate_prompt.return_value = (
            False,
            ["包含危险关键词"]
        )
        
        response = await test_client.post(
            "/api/research/start",
            json={"prompt": "危险的 prompt"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"] == "INVALID_ARGUMENT"
    
    @pytest.mark.asyncio
    async def test_missing_authorization(
        self,
        test_client: AsyncClient
    ):
        """测试缺少 Authorization header"""
        response = await test_client.post(
            "/api/research/start",
            json={"prompt": "测试查询"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "authorization" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_failed_research_task(
        self,
        test_client: AsyncClient,
        mock_genai_client
    ):
        """测试研究任务失败场景"""
        mock_client, mock_interaction = mock_genai_client
        
        # 1. 启动任务
        start_response = await test_client.post(
            "/api/research/start",
            json={"prompt": "测试失败场景"},
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert start_response.status_code == 200
        interaction_id = start_response.json()["interaction_id"]
        
        # 2. 模拟任务失败
        mock_interaction.status = "failed"
        mock_interaction.error = "Research task failed due to API error"
        
        # 3. 查询状态
        status_response = await test_client.get(
            f"/api/research/status/{interaction_id}",
            headers={"Authorization": "Bearer test_api_key_12345"}
        )
        
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "failed"
        assert "error" in status_data
        assert status_data["error"] is not None
