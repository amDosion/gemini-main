"""
Advanced Features - 基于 _interactions 模块的高级功能

集成 google.genai._interactions 的高级用法：
- 多轮对话管理
- 思考过程（thinking/thought_summary）处理
- 工具调用协调
- 状态管理
- 事件类型完整支持
"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型枚举"""
    INTERACTION_START = "interaction.start"
    CONTENT_DELTA = "content.delta"
    THINKING = "thinking"
    THOUGHT_SUMMARY = "thought_summary"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    INTERACTION_COMPLETE = "interaction.complete"
    ERROR = "error"
    STATUS_UPDATE = "status.update"


@dataclass
class ConversationState:
    """对话状态管理"""
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    thinking_history: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "in_progress"  # 'in_progress' | 'completed' | 'failed'
    interaction_id: Optional[str] = None


class AdvancedResearchAgent:
    """高级研究智能体 - 支持多轮对话和思考过程"""
    
    def __init__(
        self,
        client: Any,
        model: str,
        tools: List[Dict[str, Any]],
        config: Any
    ):
        """
        初始化高级研究智能体
        
        Args:
            client: GenAI Client 实例
            model: 模型名称
            tools: 工具列表
            config: 研究配置
        """
        self.client = client
        self.model = model
        self.tools = tools
        self.config = config
        self.conversation_state = None
        logger.info(f"[AdvancedResearchAgent] Initialized (model={model})")
    
    async def stream_research_advanced(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        高级流式研究 - 支持多轮对话和思考过程
        
        Args:
            prompt: 研究提示
            conversation_history: 对话历史（用于多轮对话）
            
        Yields:
            完整的事件流（兼容 _interactions API 格式）
        """
        import uuid
        import asyncio
        from google.genai import types as genai_types
        
        # 初始化对话状态
        session_id = str(uuid.uuid4())
        self.conversation_state = ConversationState(session_id=session_id)
        
        # 发送 interaction.start 事件
        yield {
            'event_type': EventType.INTERACTION_START,
            'interaction': {
                'id': session_id,
                'status': 'in_progress'
            },
            'event_id': f"{session_id}_start"
        }
        
        try:
            # 构建系统指令
            system_instruction = self._build_system_instruction()
            
            # 准备工具
            tools = self._prepare_tools()
            
            # 构建对话历史
            contents = self._build_contents(prompt, conversation_history)
            
            # 构建配置
            config = genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=8192,
                system_instruction=system_instruction,
                tools=tools if tools else None
            )
            
            # 流式调用模型
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config
            )
            
            # 处理流式响应
            accumulated_text = ""
            accumulated_thinking = ""
            event_id_counter = 0
            
            for chunk in stream:
                await asyncio.sleep(0)  # 让出控制权
                event_id_counter += 1
                event_id = f"{session_id}_{event_id_counter}"
                
                # 处理文本内容
                if hasattr(chunk, 'text') and chunk.text:
                    text = chunk.text
                    accumulated_text += text
                    
                    yield {
                        'event_type': EventType.CONTENT_DELTA,
                        'delta': {
                            'type': 'text',
                            'text': text
                        },
                        'event_id': event_id
                    }
                
                # 处理思考过程（如果模型支持）
                if hasattr(chunk, 'thinking') and chunk.thinking:
                    thinking_text = chunk.thinking
                    accumulated_thinking += thinking_text
                    
                    yield {
                        'event_type': EventType.CONTENT_DELTA,
                        'delta': {
                            'type': 'thought_summary',
                            'content': {
                                'text': thinking_text
                            }
                        },
                        'event_id': event_id
                    }
                
                # 处理工具调用
                if hasattr(chunk, 'function_calls') and chunk.function_calls:
                    for func_call in chunk.function_calls:
                        tool_name = getattr(func_call, 'name', 'unknown')
                        tool_args = getattr(func_call, 'args', {})
                        
                        # 记录工具调用
                        self.conversation_state.tool_calls.append({
                            'name': tool_name,
                            'args': tool_args
                        })
                        
                        yield {
                            'event_type': EventType.TOOL_CALL,
                            'tool_call': {
                                'name': tool_name,
                                'args': tool_args
                            },
                            'event_id': event_id
                        }
                        
                        # 执行工具
                        try:
                            tool_result = await self._execute_tool(tool_name, tool_args)
                            
                            self.conversation_state.tool_results.append({
                                'name': tool_name,
                                'result': tool_result
                            })
                            
                            yield {
                                'event_type': EventType.TOOL_RESULT,
                                'tool_result': tool_result,
                                'event_id': event_id
                            }
                        except Exception as e:
                            logger.error(f"[AdvancedResearchAgent] Tool execution failed: {e}")
                            yield {
                                'event_type': EventType.ERROR,
                                'error': {
                                    'type': type(e).__name__,
                                    'message': str(e),
                                    'tool': tool_name
                                },
                                'event_id': event_id
                            }
            
            # 更新状态
            self.conversation_state.status = 'completed'
            self.conversation_state.messages.append({
                'role': 'user',
                'content': prompt
            })
            self.conversation_state.messages.append({
                'role': 'model',
                'content': accumulated_text
            })
            
            # 发送完成事件
            yield {
                'event_type': EventType.INTERACTION_COMPLETE,
                'interaction': {
                    'id': session_id,
                    'status': 'completed',
                    'outputs': [{
                        'type': 'text',
                        'text': accumulated_text
                    }]
                },
                'usage': {
                    'total_tokens': len(accumulated_text) // 4  # 粗略估算
                },
                'event_id': f"{session_id}_complete"
            }
            
        except Exception as e:
            logger.error(f"[AdvancedResearchAgent] Stream research failed: {e}", exc_info=True)
            self.conversation_state.status = 'failed'
            
            # ✅ 检查是否是模型不支持标准 API 的错误
            error_message = str(e)
            if 'only supports Interactions API' in error_message or 'INVALID_ARGUMENT' in error_message:
                error_message = (
                    f"模型 {self.model} 只支持 Vertex AI Interactions API，"
                    f"不支持标准 Gemini API。请在 Vertex AI 模式下使用此模型，"
                    f"或切换到支持标准 API 的模型（如 gemini-2.0-flash-exp）。"
                )
            
            yield {
                'event_type': EventType.ERROR,
                'error': {
                    'type': type(e).__name__,
                    'message': error_message,
                    'original_error': str(e)
                },
                'event_id': f"{session_id}_error"
            }
    
    def _build_system_instruction(self) -> str:
        """构建系统指令"""
        instruction = """你是一个专业的研究助手。你的任务是：
1. 理解用户的研究需求
2. 制定详细的研究计划
3. 使用可用工具收集信息
4. 分析和整合信息
5. 生成详细的研究报告

请确保：
- 使用准确和最新的信息
- 提供详细的分析和见解
- 引用信息来源
- 结构清晰，易于理解
- 在思考过程中，简要说明你的推理步骤
"""
        return instruction
    
    def _prepare_tools(self) -> Optional[List[Any]]:
        """准备工具列表（GenAI SDK 格式）"""
        if not self.tools:
            return None
        
        try:
            from google.genai import types as genai_types
            
            genai_tools = []
            for tool in self.tools:
                tool_type = tool.get('type')
                
                if tool_type == 'google_search':
                    genai_tools.append(genai_types.Tool(
                        function_declarations=[genai_types.FunctionDeclaration(
                            name='google_search',
                            description='Search the web using Google Search',
                            parameters={
                                'type': 'object',
                                'properties': {
                                    'query': {
                                        'type': 'string',
                                        'description': 'Search query'
                                    }
                                },
                                'required': ['query']
                            }
                        )]
                    ))
                elif tool_type == 'file_search':
                    genai_tools.append(genai_types.Tool(
                        function_declarations=[genai_types.FunctionDeclaration(
                            name='file_search',
                            description='Search in uploaded documents',
                            parameters={
                                'type': 'object',
                                'properties': {
                                    'query': {
                                        'type': 'string',
                                        'description': 'Search query'
                                    },
                                    'store_names': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'File search store names'
                                    }
                                },
                                'required': ['query']
                            }
                        )]
                    ))
            
            return genai_tools if genai_tools else None
            
        except ImportError:
            logger.warning("[AdvancedResearchAgent] google.genai.types not available, tools may not work")
            return None
    
    def _build_contents(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> List[Any]:
        """构建对话内容（支持多轮对话）"""
        try:
            from google.genai import types as genai_types
            
            contents = []
            
            # 添加历史对话
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    
                    if role == 'user':
                        # 使用 Part.from_text() 类方法（需要关键字参数 text=）
                        contents.append(genai_types.Content(
                            role='user',
                            parts=[genai_types.Part.from_text(text=content)]
                        ))
                    elif role == 'model' or role == 'assistant':
                        contents.append(genai_types.Content(
                            role='model',
                            parts=[genai_types.Part.from_text(text=content)]
                        ))
            
            # 添加当前提示
            contents.append(genai_types.Content(
                role='user',
                parts=[genai_types.Part.from_text(text=prompt)]
            ))
            
            return contents
            
        except ImportError:
            # 如果导入失败，返回简单的字符串列表
            return [prompt]
    
    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        # 导入 ToolManager 来执行工具
        try:
            from .tools import ToolManager
            
            # 创建临时 ToolManager（使用空工具列表，因为工具已经在 ResearchAgent 中注册）
            # 实际上，我们应该从 ResearchAgent 获取 ToolManager
            # 但为了简化，这里直接导入 Browser 工具
            if tool_name in ['web_search', 'read_webpage', 'selenium_browse']:
                # Browser 工具
                from ...gemini.browser import AVAILABLE_TOOLS
                
                if tool_name not in AVAILABLE_TOOLS:
                    return {'error': f'Browser tool {tool_name} not found'}
                
                tool_func = AVAILABLE_TOOLS[tool_name]
                logger.info(f"[AdvancedResearchAgent] Executing browser tool: {tool_name} with args: {args}")
                
                # 执行工具（可能是同步或异步）
                import asyncio
                if asyncio.iscoroutinefunction(tool_func):
                    result = await tool_func(**args)
                else:
                    result = await asyncio.to_thread(tool_func, **args)
                
                # 处理 selenium_browse 返回的结构化响应
                if tool_name == 'selenium_browse':
                    if isinstance(result, dict):
                        if result.get('error'):
                            return {'error': result['error']}
                        else:
                            return {
                                'result': result.get('content', ''),
                                'screenshot': result.get('screenshot'),
                                'success': True
                            }
                
                # 其他工具返回字符串
                return {
                    'result': result if isinstance(result, str) else str(result),
                    'success': True
                }
            else:
                # 其他工具（TODO: 实现具体逻辑）
                logger.info(f"[AdvancedResearchAgent] Executing tool: {tool_name} with args: {args}")
                return {
                    'error': f'Tool {tool_name} execution not yet implemented'
                }
        except Exception as e:
            logger.error(f"[AdvancedResearchAgent] Tool execution failed: {e}", exc_info=True)
            return {
                'error': str(e)
            }
    
    def get_conversation_state(self) -> Optional[ConversationState]:
        """获取当前对话状态"""
        return self.conversation_state
