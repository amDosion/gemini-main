---
inclusion: fileMatch
fileMatchPattern: "backend/**/*.py"
---

# 后端开发规范

## 核心原则

### 1. 服务模块化（第一原则）⭐

**每个服务功能必须单独文件，主文件负责协调**

#### 正确示例

```
backend/app/services/gemini/
├── google_service.py      # 主协调器（100 行）
├── chat_handler.py        # 聊天模块（200 行）
├── image_generator.py     # 图像生成模块（250 行）
├── video_generator.py     # 视频生成模块（200 行）
├── model_manager.py       # 模型管理模块（150 行）
└── file_handler.py        # 文件处理模块（100 行）
```

```python
# google_service.py - 主协调器
from ..base_provider import BaseProviderService
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .model_manager import ModelManager

class GoogleService(BaseProviderService):
    """Google Gemini 服务主协调器
    
    职责：组装和协调各个功能模块
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)
        
        # 组装功能模块
        self.chat_handler = ChatHandler(api_key)
        self.image_generator = ImageGenerator(api_key)
        self.model_manager = ModelManager(api_key)

    def send_chat_message(self, messages, model, **kwargs):
        """协调聊天功能"""
        return self.chat_handler.send_message(messages, model, **kwargs)

    def generate_image(self, prompt, **kwargs):
        """协调图像生成功能"""
        return self.image_generator.generate(prompt, **kwargs)

    def get_available_models(self):
        """协调模型管理功能"""
        return self.model_manager.list_models()
```

**文件大小限制**：单个文件不超过 300 行

---

## 架构模式

### 三层架构

```
Router 层（API 端点）
    ↓
Service 层（业务逻辑）
    ↓
Model 层（数据模型）
```

### 路由层示例

```python
# backend/app/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.database import get_db
from ..core.user_context import require_user_id
from ..services.provider_factory import ProviderFactory

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    """聊天请求模型"""
    session_id: str
    message: str
    model: str
    provider: str

class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: str
    role: str
    timestamp: int

@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user_id: int = Depends(require_user_id),
    db: AsyncSession = Depends(get_db)
):
    """发送聊天消息
    
    Args:
        request: 聊天请求
        user_id: 用户 ID（自动注入）
        db: 数据库会话（自动注入）
        
    Returns:
        ChatResponse: 聊天响应
        
    Raises:
        HTTPException: 400 - 无效请求
        HTTPException: 500 - 服务器错误
    """
    try:
        # 获取提供商服务
        provider = ProviderFactory.get_provider(
            request.provider,
            user_id,
            db
        )
        
        # 调用服务层
        result = await provider.send_chat_message(
            messages=[{"role": "user", "content": request.message}],
            model=request.model
        )
        
        return ChatResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 错误处理

### 自定义异常

```python
# backend/app/core/exceptions.py
class BaseAPIException(Exception):
    """API 异常基类"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class ValidationError(BaseAPIException):
    """验证错误"""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

class AuthenticationError(BaseAPIException):
    """认证错误"""
    def __init__(self, message: str):
        super().__init__(message, status_code=401)

class ProviderError(BaseAPIException):
    """提供商错误"""
    def __init__(self, message: str):
        super().__init__(message, status_code=502)
```

### 错误处理示例

```python
# backend/app/services/gemini/chat_handler.py
from ...core.exceptions import ProviderError, ValidationError

class ChatHandler:
    async def send_message(self, messages, model, **kwargs):
        """发送聊天消息
        
        Raises:
            ValidationError: 输入验证失败
            ProviderError: API 调用失败
        """
        # 输入验证
        if not messages:
            raise ValidationError("消息列表不能为空")
        
        if not model:
            raise ValidationError("模型名称不能为空")
        
        try:
            # API 调用
            response = await self.client.generate_content(
                messages=messages,
                model=model,
                **kwargs
            )
            return response
            
        except Exception as e:
            raise ProviderError(f"Gemini API 调用失败: {str(e)}")
```

---

## 依赖注入

### 数据库会话注入

```python
# backend/app/core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine("sqlite+aiosqlite:///./database.db")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session
```

### 用户上下文注入

```python
# backend/app/core/user_context.py
from fastapi import Header, HTTPException

async def require_user_id(x_user_id: str = Header(...)) -> int:
    """从请求头获取用户 ID
    
    Args:
        x_user_id: 用户 ID 请求头
        
    Returns:
        int: 用户 ID
        
    Raises:
        HTTPException: 401 - 缺少用户 ID
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="缺少用户 ID")
    
    try:
        return int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的用户 ID")
```

---

## 数据模型

### SQLAlchemy 模型

```python
# backend/app/models/chat_session.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from ..core.database import Base

class ChatSession(Base):
    """聊天会话模型"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, unique=True, nullable=False, index=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id={self.session_id})>"
```

### Pydantic 模型

```python
# backend/app/schemas/chat.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime

class ChatMessageBase(BaseModel):
    """聊天消息基础模型"""
    role: str = Field(..., description="消息角色（user/assistant）")
    content: str = Field(..., description="消息内容")

    @validator("role")
    def validate_role(cls, v):
        if v not in ["user", "assistant", "system"]:
            raise ValueError("角色必须是 user、assistant 或 system")
        return v

class ChatMessageCreate(ChatMessageBase):
    """创建聊天消息模型"""
    session_id: str = Field(..., description="会话 ID")

class ChatMessageResponse(ChatMessageBase):
    """聊天消息响应模型"""
    id: int
    session_id: str
    timestamp: datetime

    class Config:
        from_attributes = True
```

---

## 测试规范

### 单元测试

```python
# backend/tests/test_chat_handler.py
import pytest
from unittest.mock import Mock, AsyncMock
from app.services.gemini.chat_handler import ChatHandler
from app.core.exceptions import ValidationError, ProviderError

@pytest.fixture
def chat_handler():
    """创建 ChatHandler 实例"""
    return ChatHandler(api_key="test_key")

@pytest.mark.asyncio
async def test_send_message_success(chat_handler):
    """测试发送消息成功"""
    # 模拟 API 响应
    chat_handler.client.generate_content = AsyncMock(
        return_value={"message": "Hello!", "role": "assistant"}
    )
    
    # 调用方法
    result = await chat_handler.send_message(
        messages=[{"role": "user", "content": "Hi"}],
        model="gemini-pro"
    )
    
    # 验证结果
    assert result["message"] == "Hello!"
    assert result["role"] == "assistant"

@pytest.mark.asyncio
async def test_send_message_empty_messages(chat_handler):
    """测试空消息列表"""
    with pytest.raises(ValidationError) as exc_info:
        await chat_handler.send_message(messages=[], model="gemini-pro")
    
    assert "消息列表不能为空" in str(exc_info.value)

@pytest.mark.asyncio
async def test_send_message_api_error(chat_handler):
    """测试 API 错误"""
    # 模拟 API 错误
    chat_handler.client.generate_content = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    with pytest.raises(ProviderError) as exc_info:
        await chat_handler.send_message(
            messages=[{"role": "user", "content": "Hi"}],
            model="gemini-pro"
        )
    
    assert "Gemini API 调用失败" in str(exc_info.value)
```

### 集成测试

```python
# backend/tests/test_chat_api.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_send_chat_message_success():
    """测试聊天 API 端点"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/",
            json={
                "session_id": "test_session",
                "message": "Hello",
                "model": "gemini-pro",
                "provider": "google"
            },
            headers={"X-User-Id": "1"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "role" in data
    assert data["role"] == "assistant"

@pytest.mark.asyncio
async def test_send_chat_message_missing_user_id():
    """测试缺少用户 ID"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/",
            json={
                "session_id": "test_session",
                "message": "Hello",
                "model": "gemini-pro",
                "provider": "google"
            }
        )
    
    assert response.status_code == 401
    assert "缺少用户 ID" in response.json()["detail"]
```

---

## 开发检查清单

### 开发前

- [ ] 阅读相关 Spec 文档（requirements.md, design.md）
- [ ] 理解现有架构和模式
- [ ] 确认依赖关系和接口
- [ ] 规划模块拆分（每个文件 < 300 行）

### 开发中

- [ ] 遵循三层架构（Router → Service → Model）
- [ ] 使用依赖注入（数据库会话、用户上下文）
- [ ] 添加类型注解（所有函数参数和返回值）
- [ ] 使用 Pydantic 模型验证输入
- [ ] 实现自定义异常处理
- [ ] 添加详细的文档字符串
- [ ] 编写单元测试（覆盖率 > 80%）

### 开发后

- [ ] 运行所有测试（pytest）
- [ ] 检查代码覆盖率（pytest-cov）
- [ ] 运行代码检查（ruff）
- [ ] 验证 API 端点（手动测试或集成测试）
- [ ] 更新 API 文档
- [ ] 提交代码前检查 git diff
