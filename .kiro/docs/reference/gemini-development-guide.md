# Google Gemini 开发详细指南

## 概述

本文档提供 Google Gemini 相关功能开发的详细指南，包括完整的代码示例、最佳实践和故障排除方案。

---

## 1. 核心参考文档

### 1.1 必读文档列表

在开发任何 Gemini 相关功能之前，**必须**先阅读和理解以下文档：

| 文档路径 | 用途 | 优先级 |
|---------|------|--------|
| `D:\gemini-main\gemini-main\.kiro\specs\参考\python-genai-main\google-genai-models-usage.md` | Gemini 模型使用指南 | 🔴 必读 |
| `D:\gemini-main\gemini-main\.kiro\specs\参考\python-genai-main\google-genai-live-api-usage.md` | Gemini Live API 使用指南 | 🔴 必读 |
| `D:\gemini-main\gemini-main\.kiro\specs\参考\python-genai-main\google\genai\` | Google GenAI SDK 原始代码 | 🟡 参考 |

### 1.2 文档使用场景

| 开发场景 | 必须参考的文档 |
|---------|---------------|
| **新增 Gemini 模型支持** | `google-genai-models-usage.md` + SDK 原始代码 |
| **实现流式响应** | `google-genai-live-api-usage.md` + SDK 原始代码 |
| **图像生成功能** | `google-genai-models-usage.md` (Imagen 部分) |
| **视频生成功能** | `google-genai-models-usage.md` (Veo 部分) |
| **多模态输入处理** | `google-genai-models-usage.md` + `google-genai-live-api-usage.md` |
| **错误处理和重试** | SDK 原始代码 (异常处理部分) |
| **API 参数配置** | `google-genai-models-usage.md` + SDK 原始代码 |

---

## 2. 开发流程规范

### 2.1 功能开发前置步骤

在开始编写代码之前，必须完成以下步骤：

```
1. 阅读相关参考文档
   └─ 理解 API 使用方法和参数
   └─ 了解错误处理机制
   └─ 掌握最佳实践

2. 查看 SDK 原始代码
   └─ 理解数据结构定义
   └─ 学习异常处理模式
   └─ 参考实现细节

3. 设计实现方案
   └─ 确定接口设计
   └─ 规划错误处理
   └─ 考虑性能优化

4. 编写代码
   └─ 遵循项目架构模式
   └─ 实现完整的错误处理
   └─ 添加必要的日志记录

5. 测试验证
   └─ 单元测试
   └─ 集成测试
   └─ 端到端测试
```

### 2.2 代码实现规范

**后端实现规范**：

```python
# 1. 必须继承 BaseProviderService
from app.services.base_provider import BaseProviderService

class GeminiService(BaseProviderService):
    """
    Google Gemini 服务实现
    
    参考文档：
    - google-genai-models-usage.md
    - google-genai-live-api-usage.md
    """
    
    def __init__(self, api_key: str):
        """
        初始化 Gemini 服务
        
        Args:
            api_key: Google API 密钥
            
        参考：SDK 原始代码 google/genai/client.py
        """
        super().__init__(api_key)
        # 初始化逻辑
    
    async def send_chat_message(
        self,
        messages: List[Dict],
        model: str,
        **kwargs
    ) -> Dict:
        """
        发送聊天消息
        
        Args:
            messages: 消息列表
            model: 模型 ID
            **kwargs: 额外参数
            
        Returns:
            响应字典
            
        参考：
        - google-genai-models-usage.md (Chat API 部分)
        - SDK 原始代码 google/genai/chats.py
        """
        try:
            # 实现逻辑
            pass
        except Exception as e:
            # 错误处理（参考 SDK 异常处理）
            self._handle_error(e)
    
    async def handle_streaming_response(
        self,
        stream: AsyncIterator,
        callback: Callable
    ) -> None:
        """
        处理流式响应
        
        参考：
        - google-genai-live-api-usage.md
        - SDK 原始代码 google/genai/live.py
        """
        try:
            async for chunk in stream:
                await callback(chunk)
        except Exception as e:
            self._handle_error(e)
```

**前端实现规范**：

```typescript
// 1. 必须实现 AIProvider 接口
import { AIProvider, Message, StreamCallback } from '@/types';

/**
 * Google Gemini 提供商客户端
 * 
 * 参考文档：
 * - google-genai-models-usage.md
 * - google-genai-live-api-usage.md
 */
export class GeminiProvider implements AIProvider {
  constructor(private apiKey: string) {}

  /**
   * 发送消息
   * 
   * 参考：google-genai-models-usage.md (Chat API 部分)
   */
  async sendMessage(
    messages: Message[],
    model: string,
    options?: Record<string, any>
  ): Promise<Message> {
    try {
      // 实现逻辑
    } catch (error) {
      // 错误处理
      this.handleError(error);
    }
  }

  /**
   * 流式消息
   * 
   * 参考：google-genai-live-api-usage.md
   */
  async streamMessage(
    messages: Message[],
    model: string,
    callback: StreamCallback,
    options?: Record<string, any>
  ): Promise<void> {
    try {
      // 实现逻辑
    } catch (error) {
      this.handleError(error);
    }
  }
}
```

---

## 3. 关键实现要点

### 3.1 模型配置

**必须参考**：`google-genai-models-usage.md`

```python
# 后端配置示例
GEMINI_MODELS = {
    "gemini-2.0-flash-exp": {
        "name": "Gemini 2.0 Flash (Experimental)",
        "capabilities": ["chat", "vision", "code"],
        "context_window": 1048576,  # 1M tokens
        "max_output_tokens": 8192,
        "supports_streaming": True,
        "supports_function_calling": True,
    },
    "gemini-2.5-flash-preview": {
        "name": "Gemini 2.5 Flash (Preview)",
        "capabilities": ["chat", "vision", "code", "audio"],
        "context_window": 1048576,
        "max_output_tokens": 8192,
        "supports_streaming": True,
        "supports_function_calling": True,
    },
    "imagen-3.0-generate-001": {
        "name": "Imagen 3.0",
        "capabilities": ["image-generation"],
        "max_images": 4,
        "supported_aspect_ratios": ["1:1", "3:4", "4:3", "9:16", "16:9"],
    },
}
```

### 3.2 流式响应处理

**必须参考**：`google-genai-live-api-usage.md`

```python
# 后端流式处理示例
async def stream_chat_response(
    self,
    messages: List[Dict],
    model: str
) -> AsyncIterator[str]:
    """
    流式聊天响应
    
    参考：google-genai-live-api-usage.md
    """
    try:
        # 创建流式会话
        session = await self.client.aio.live.connect(
            model=model,
            config={"response_modalities": ["TEXT"]}
        )
        
        # 发送消息
        await session.send(messages[-1]["content"])
        
        # 接收流式响应
        async for chunk in session.receive():
            if chunk.text:
                yield chunk.text
                
    except Exception as e:
        # 错误处理
        logger.error(f"Stream error: {e}")
        raise
    finally:
        # 清理资源
        await session.close()
```

### 3.3 错误处理

**必须参考**：SDK 原始代码 `google/genai/errors.py`

```python
# 错误处理示例
from google.genai import errors

def _handle_error(self, error: Exception) -> None:
    """
    统一错误处理
    
    参考：SDK 原始代码 google/genai/errors.py
    """
    if isinstance(error, errors.AuthenticationError):
        raise APIError("认证失败：API 密钥无效", status_code=401)
    elif isinstance(error, errors.RateLimitError):
        raise APIError("速率限制：请求过于频繁", status_code=429)
    elif isinstance(error, errors.InvalidRequestError):
        raise APIError(f"请求无效：{str(error)}", status_code=400)
    elif isinstance(error, errors.ServerError):
        raise APIError("服务器错误：请稍后重试", status_code=500)
    else:
        raise APIError(f"未知错误：{str(error)}", status_code=500)
```

### 3.4 多模态输入处理

**必须参考**：`google-genai-models-usage.md` (Multimodal 部分)

```python
# 多模态输入示例
async def send_multimodal_message(
    self,
    text: str,
    images: List[bytes] = None,
    audio: bytes = None,
    model: str = "gemini-2.5-flash-preview"
) -> Dict:
    """
    发送多模态消息
    
    参考：google-genai-models-usage.md (Multimodal Input 部分)
    """
    contents = [{"role": "user", "parts": []}]
    
    # 添加文本
    if text:
        contents[0]["parts"].append({"text": text})
    
    # 添加图像
    if images:
        for image in images:
            contents[0]["parts"].append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(image).decode()
                }
            })
    
    # 添加音频
    if audio:
        contents[0]["parts"].append({
            "inline_data": {
                "mime_type": "audio/wav",
                "data": base64.b64encode(audio).decode()
            }
        })
    
    # 发送请求
    response = await self.client.aio.models.generate_content(
        model=model,
        contents=contents
    )
    
    return response
```

---

## 4. 测试规范

### 4.1 单元测试

```python
# tests/test_gemini_service.py
import pytest
from app.services.gemini.service import GeminiService

class TestGeminiService:
    """
    Gemini 服务单元测试
    
    参考：google-genai-models-usage.md
    """
    
    @pytest.fixture
    def service(self):
        return GeminiService(api_key="test_key")
    
    async def test_send_chat_message_success(self, service):
        """测试成功发送聊天消息"""
        response = await service.send_chat_message(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-2.0-flash-exp"
        )
        assert response["status"] == "success"
        assert "content" in response
    
    async def test_send_chat_message_invalid_api_key(self):
        """测试无效 API 密钥"""
        service = GeminiService(api_key="invalid")
        with pytest.raises(APIError) as exc:
            await service.send_chat_message(
                messages=[{"role": "user", "content": "Hello"}],
                model="gemini-2.0-flash-exp"
            )
        assert exc.value.status_code == 401
```

### 4.2 集成测试

```python
# tests/integration/test_gemini_integration.py
import pytest
from app.services.gemini.service import GeminiService

@pytest.mark.integration
class TestGeminiIntegration:
    """
    Gemini 集成测试
    
    参考：
    - google-genai-models-usage.md
    - google-genai-live-api-usage.md
    """
    
    async def test_end_to_end_chat(self):
        """端到端聊天测试"""
        service = GeminiService(api_key=os.getenv("GOOGLE_API_KEY"))
        
        # 发送消息
        response = await service.send_chat_message(
            messages=[{"role": "user", "content": "What is AI?"}],
            model="gemini-2.0-flash-exp"
        )
        
        # 验证响应
        assert response["status"] == "success"
        assert len(response["content"]) > 0
        assert "usage" in response
```

---

## 5. 文档更新规范

### 5.1 代码注释

所有 Gemini 相关代码必须包含：

1. **函数/类文档字符串**：
   - 功能描述
   - 参数说明
   - 返回值说明
   - 参考文档链接

2. **关键逻辑注释**：
   - 复杂算法说明
   - 特殊处理逻辑
   - 参考 SDK 原始代码位置

### 5.2 API 文档

新增或修改 Gemini API 时，必须更新：

- `docs/api/gemini.md` - API 端点文档
- `README.md` - 功能列表和使用说明
- `CHANGELOG.md` - 变更记录

---

## 6. 常见问题和解决方案

### 6.1 API 密钥管理

**问题**：如何安全管理 Google API 密钥？

**解决方案**：
```python
# 使用环境变量
import os
from app.core.config import settings

api_key = settings.GOOGLE_API_KEY  # 从配置读取

# 或使用密钥管理服务
from app.services.secrets import get_secret
api_key = await get_secret("google_api_key")
```

### 6.2 速率限制处理

**问题**：如何处理 API 速率限制？

**解决方案**：
```python
# 参考：SDK 原始代码 google/genai/client.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def send_with_retry(self, *args, **kwargs):
    """带重试的发送"""
    try:
        return await self.send_chat_message(*args, **kwargs)
    except errors.RateLimitError:
        logger.warning("Rate limit hit, retrying...")
        raise
```

### 6.3 大文件处理

**问题**：如何处理大型图像或音频文件？

**解决方案**：
```python
# 参考：google-genai-models-usage.md (File Upload 部分)
async def upload_large_file(self, file_path: str) -> str:
    """上传大文件到 Google Cloud Storage"""
    # 使用 File API 上传
    file = await self.client.aio.files.upload(file_path)
    return file.uri
```

---

## 7. 检查清单

在提交 Gemini 相关代码前，必须确认：

- [ ] 已阅读所有必读参考文档
- [ ] 已查看 SDK 原始代码实现
- [ ] 代码遵循项目架构模式
- [ ] 实现了完整的错误处理
- [ ] 添加了必要的日志记录
- [ ] 编写了单元测试
- [ ] 编写了集成测试
- [ ] 更新了 API 文档
- [ ] 添加了代码注释和文档字符串
- [ ] 通过了所有测试
- [ ] 进行了代码审查

---

## 8. 参考资源

### 8.1 官方文档

- [Google AI Studio](https://aistudio.google.com/)
- [Gemini API 文档](https://ai.google.dev/docs)
- [Python SDK 文档](https://github.com/google/generative-ai-python)

### 8.2 项目文档

- [项目架构文档](../../docs/ARCHITECTURE.md)
- [API 开发指南](../../docs/API_DEVELOPMENT.md)
- [测试指南](../../docs/TESTING.md)

### 8.3 相关规范

- [MCP 协作规范](#[[file:.kiro/docs/collaboration/mcp-collaboration-guide.md]])
- [主 Agent 协作规则](#[[file:.kiro/steering/Agents.md]])
- [代码质量标准](./code-quality.md)

---

**版本**: 1.0.0  
**更新日期**: 2026-01-09  
**维护者**: Development Team
