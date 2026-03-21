"""
Research Agent - 研究智能体核心逻辑

实现基于 Gemini API 的研究流程
"""

import logging
import uuid
from typing import Dict, Any, Optional, List, AsyncGenerator
from .types import ResearchConfig, ResearchResult, StreamEvent
from .tools import ToolManager, is_url

logger = logging.getLogger(__name__)


class ResearchAgent:
    """研究智能体 - 实现多轮对话研究流程"""
    
    def __init__(
        self,
        client: Any,
        model: str,
        tools: List[Dict[str, Any]],
        config: ResearchConfig
    ):
        """
        初始化研究智能体
        
        Args:
            client: GenAI Client 实例
            model: 模型名称
            tools: 工具列表
            config: 研究配置
        """
        self.client = client
        self.model = model
        self.tool_manager = ToolManager(tools)
        self.config = config
        self.session_id = str(uuid.uuid4())
        logger.info(f"[ResearchAgent] Initialized (session_id={self.session_id})")
    
    async def execute(self, prompt: str) -> ResearchResult:
        """
        执行研究任务（非流式）
        
        Args:
            prompt: 研究提示
            
        Returns:
            研究结果
        """
        try:
            # 构建系统指令
            system_instruction = self._build_system_instruction()
            
            # 准备工具
            tools = self.tool_manager.get_tools()
            
            # 构建配置（system_instruction 应该放在 config 中）
            try:
                from google.genai import types as genai_types
                
                config = genai_types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=8192,
                    system_instruction=system_instruction,
                    tools=tools if tools else None
                )
            except ImportError:
                # 如果导入失败，使用字典格式
                config = {
                    'temperature': 0.7,
                    'max_output_tokens': 8192,
                    'system_instruction': system_instruction,
                    'tools': tools if tools else None
                }
            
            # 调用模型（使用正确的 genai SDK API）
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )
            
            # 处理响应
            outputs = []
            if hasattr(response, 'text'):
                outputs.append({
                    'type': 'text',
                    'text': response.text
                })
            
            return ResearchResult(
                session_id=self.session_id,
                status='completed',
                outputs=outputs
            )
            
        except Exception as e:
            logger.error(f"[ResearchAgent] Execution failed: {e}", exc_info=True)
            return ResearchResult(
                session_id=self.session_id,
                status='failed',
                outputs=[],
                error=str(e)
            )
    
    async def stream_execute(self, prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行研究任务（支持函数调用循环）
        
        Args:
            prompt: 研究提示
            
        Yields:
            流式事件
        """
        try:
            # 构建系统指令
            system_instruction = self._build_system_instruction()
            
            # 准备工具
            tools = self.tool_manager.get_tools()
            
            # 记录工具信息
            if tools:
                logger.info(f"[ResearchAgent] Tools prepared: {len(tools)} tool(s)")
                for tool in tools:
                    if hasattr(tool, 'function_declarations'):
                        for fd in tool.function_declarations:
                            logger.info(f"[ResearchAgent] Tool: {fd.name} - {fd.description[:60]}...")
                    elif isinstance(tool, dict):
                        for fd in tool.get('function_declarations', []):
                            logger.info(f"[ResearchAgent] Tool: {fd.get('name')} - {fd.get('description', '')[:60]}...")
            else:
                logger.warning(f"[ResearchAgent] No tools available")
            
            # 构建配置（system_instruction 应该放在 config 中）
            from google.genai import types as genai_types
            import asyncio
            
            # 发送 interaction.start 事件（兼容 _interactions API）
            yield {
                'event_type': 'interaction.start',
                'interaction': {
                    'id': self.session_id,
                    'status': 'in_progress'
                },
                'event_id': f"{self.session_id}_start"
            }
            
            # 函数调用循环（类似 chat_handler.py）
            max_iterations = 5
            current_content = prompt
            accumulated_text = ""
            accumulated_thinking = ""
            event_id_counter = 0
            
            for iteration in range(max_iterations):
                logger.info(f"[ResearchAgent] Function call loop iteration {iteration + 1}/{max_iterations}")
                
                # 构建配置
                config = genai_types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=8192,
                    system_instruction=system_instruction,
                    tools=tools if tools else None
                )
                
                # 流式调用模型
                # 注意：第一次迭代时 current_content 是字符串，后续迭代是 Content 对象列表
                # genai SDK 的 generate_content_stream 支持 Union[str, Content, list]
                logger.debug(f"[ResearchAgent] Iteration {iteration + 1}: contents type = {type(current_content)}")
                if tools:
                    logger.info(f"[ResearchAgent] Iteration {iteration + 1}: {len(tools)} tools available")
                    # 记录工具名称
                    tool_names = []
                    for tool in tools:
                        if hasattr(tool, 'function_declarations'):
                            for fd in tool.function_declarations:
                                tool_names.append(fd.name)
                        elif isinstance(tool, dict) and 'function_declarations' in tool:
                            for fd in tool['function_declarations']:
                                tool_names.append(fd.get('name', 'unknown'))
                    if tool_names:
                        logger.info(f"[ResearchAgent] Available tools: {tool_names}")
                
                stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=current_content,  # 支持 str 或 Content 对象列表
                    config=config
                )
                
                # 收集函数调用
                function_calls = []
                iteration_text = ""
                
                # 处理流式响应
                for chunk in stream:
                    await asyncio.sleep(0)  # 让出控制权
                    event_id_counter += 1
                    event_id = f"{self.session_id}_{iteration}_{event_id_counter}"
                    
                    # 提取文本
                    if hasattr(chunk, 'text') and chunk.text:
                        text = chunk.text
                        iteration_text += text
                        accumulated_text += text
                        
                        yield {
                            'event_type': 'content.delta',
                            'delta': {
                                'type': 'text',
                                'text': text
                            },
                            'event_id': event_id
                        }
                    
                    # 提取思考过程
                    if hasattr(chunk, 'thinking') and chunk.thinking:
                        thinking_text = chunk.thinking
                        accumulated_thinking += thinking_text
                        
                        yield {
                            'event_type': 'content.delta',
                            'delta': {
                                'type': 'thought_summary',
                                'content': {
                                    'text': thinking_text
                                }
                            },
                            'event_id': event_id
                        }
                    
                    # 检测函数调用
                    # 注意：genai SDK 的流式响应中，function_calls 可能在多个位置
                    try:
                        # 方法1: 检查 candidates -> content -> parts -> function_call
                        if hasattr(chunk, 'candidates') and chunk.candidates:
                            candidate = chunk.candidates[0]
                            if hasattr(candidate, 'content') and candidate.content:
                                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                    for part in candidate.content.parts:
                                        if hasattr(part, 'function_call') and part.function_call:
                                            if part.function_call not in function_calls:
                                                function_calls.append(part.function_call)
                                                logger.info(f"[ResearchAgent] ✅ Detected function_call (via candidates): {part.function_call.name}")
                        
                        # 方法2: 直接检查 function_calls 属性
                        if hasattr(chunk, 'function_calls') and chunk.function_calls:
                            for func_call in chunk.function_calls:
                                if func_call not in function_calls:
                                    function_calls.append(func_call)
                                    logger.info(f"[ResearchAgent] ✅ Detected function_call (direct): {getattr(func_call, 'name', 'unknown')}")
                        
                        # 方法3: 检查 finish_reason（如果是 FUNCTION_CALL）
                        if hasattr(chunk, 'candidates') and chunk.candidates:
                            candidate = chunk.candidates[0]
                            if hasattr(candidate, 'finish_reason'):
                                # finish_reason 可能是枚举值，检查是否是函数调用
                                finish_reason = candidate.finish_reason
                                if finish_reason and (finish_reason == 2 or str(finish_reason).lower() == 'function_call'):
                                    logger.debug(f"[ResearchAgent] Finish reason indicates function call: {finish_reason}")
                    except Exception as e:
                        logger.debug(f"[ResearchAgent] Failed to extract function_call from chunk: {e}")
                
                # 如果没有函数调用，退出循环
                if not function_calls:
                    logger.info(f"[ResearchAgent] No function calls detected, exiting loop")
                    break
                
                # 执行函数调用并构建响应
                logger.info(f"[ResearchAgent] Detected {len(function_calls)} function call(s)")
                
                function_response_parts = []
                
                for func_call in function_calls:
                    tool_name = getattr(func_call, 'name', 'unknown')
                    tool_args = dict(getattr(func_call, 'args', {})) if hasattr(func_call, 'args') else {}
                    
                    logger.info(f"[ResearchAgent] Executing function: {tool_name} with args: {tool_args}")
                    
                    # 发送工具调用事件
                    yield {
                        'event_type': 'tool.call',
                        'tool_call': {
                            'name': tool_name,
                            'args': tool_args
                        },
                        'event_id': f"{self.session_id}_tool_{tool_name}"
                    }
                    
                    # 执行工具
                    try:
                        tool_result = await self.tool_manager.execute_tool(
                            tool_name,
                            tool_args
                        )
                        
                        # 处理 Browser 工具的特殊返回格式
                        response_data = {}
                        screenshot_base64 = None
                        
                        if tool_name in ['web_search', 'read_webpage', 'selenium_browse']:
                            if tool_result.get('error'):
                                response_data = {"error": tool_result['error']}
                            else:
                                result_content = tool_result.get('result', '')
                                response_data = {"output": result_content}
                                screenshot_base64 = tool_result.get('screenshot')
                                
                                # 发送工具结果事件
                                yield {
                                    'event_type': 'tool.result',
                                    'tool_result': {
                                        'result': result_content[:500] if result_content else '',  # 截断显示
                                        'tool': tool_name,
                                        'has_screenshot': screenshot_base64 is not None
                                    },
                                    'event_id': f"{self.session_id}_result_{tool_name}"
                                }
                        else:
                            # 其他工具
                            if tool_result.get('error'):
                                response_data = {"error": tool_result['error']}
                            else:
                                response_data = {"output": str(tool_result.get('result', ''))}
                            
                            yield {
                                'event_type': 'tool.result',
                                'tool_result': tool_result,
                                'event_id': f"{self.session_id}_result_{tool_name}"
                            }
                        
                        # 创建函数响应 Part
                        response_part = genai_types.Part.from_function_response(
                            name=tool_name,
                            response=response_data
                        )
                        function_response_parts.append(response_part)
                        
                        # 如果有截图，添加图片 Part（selenium_browse）
                        if screenshot_base64 and tool_name == 'selenium_browse':
                            try:
                                import base64
                                image_bytes = base64.b64decode(screenshot_base64)
                                image_part = genai_types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type="image/png"
                                )
                                function_response_parts.append(image_part)
                                logger.info(f"[ResearchAgent] Added screenshot image to response")
                            except Exception as e:
                                logger.warning(f"[ResearchAgent] Failed to add screenshot: {e}")
                        
                    except Exception as e:
                        logger.error(f"[ResearchAgent] Tool execution failed: {e}", exc_info=True)
                        response_data = {"error": str(e)}
                        response_part = genai_types.Part.from_function_response(
                            name=tool_name,
                            response=response_data
                        )
                        function_response_parts.append(response_part)
                        
                        yield {
                            'event_type': 'error',
                            'error': {
                                'type': type(e).__name__,
                                'message': str(e),
                                'tool': tool_name
                            },
                            'event_id': f"{self.session_id}_error_{tool_name}"
                        }
                
                # 将函数响应作为下一条消息发送（继续循环）
                if function_response_parts:
                    # 构建新的消息内容（包含函数响应）
                    # 注意：genai SDK 需要 Content 对象列表
                    current_content = [
                        genai_types.Content(
                            role="user",
                            parts=function_response_parts
                        )
                    ]
                    logger.info(f"[ResearchAgent] Sending {len(function_response_parts)} function response(s) to model for next iteration")
                else:
                    # 如果没有函数响应，退出循环
                    logger.warning(f"[ResearchAgent] No function responses generated, exiting loop")
                    break
            
            # 完成事件（兼容 _interactions API 格式）
            yield {
                'event_type': 'interaction.complete',
                'interaction': {
                    'id': self.session_id,
                    'status': 'completed',
                    'outputs': [{
                        'type': 'text',
                        'text': accumulated_text
                    }] if accumulated_text else []
                },
                'usage': {
                    'total_tokens': len(accumulated_text) // 4  # 粗略估算
                },
                'event_id': f"{self.session_id}_complete"
            }
            
        except Exception as e:
            logger.error(f"[ResearchAgent] Stream execution failed: {e}", exc_info=True)
            
            # ✅ 检查是否是模型不支持标准 API 的错误
            error_message = str(e)
            if 'only supports Interactions API' in error_message or 'INVALID_ARGUMENT' in error_message:
                error_message = (
                    f"模型 {self.model} 只支持 Vertex AI Interactions API，"
                    f"不支持标准 Gemini API。请在 Vertex AI 模式下使用此模型，"
                    f"或切换到支持标准 API 的模型（如 gemini-2.0-flash-exp）。"
                )
            
            yield {
                'event_type': 'error',
                'error': {
                    'type': type(e).__name__,
                    'message': error_message,
                    'original_error': str(e)
                }
            }
    
    def _build_system_instruction(self) -> str:
        """构建系统指令"""
        instruction = """你是一个专业的研究助手。你的任务是：
1. 理解用户的研究需求
2. 制定研究计划
3. 使用可用工具收集信息
4. 分析和整合信息
5. 生成详细的研究报告

请确保：
- 使用准确和最新的信息
- 提供详细的分析和见解
- 引用信息来源
- 结构清晰，易于理解
"""
        
        if self.config.thinking_summaries == 'auto':
            instruction += "\n在思考过程中，请简要说明你的推理步骤。"
        
        return instruction
