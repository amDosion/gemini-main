"""
Interactions API 核心服务

提供统一的接口用于创建、查询、删除交互
"""

from typing import Optional, List, Union, Dict, Any, AsyncIterator
from datetime import datetime
import logging

from google import genai
from google.genai.types import Content, Tool, GenerationConfig, Part

from .state_manager import StateManager
from .tool_orchestrator import ToolOrchestrator
from ..utils.error_handler import handle_gemini_error


logger = logging.getLogger(__name__)


def validate_generation_config(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    验证 generation_config 参数
    
    Args:
        config: 生成配置字典
        
    Returns:
        验证后的配置字典
        
    Raises:
        ValueError: 参数验证失败
    """
    if config is None:
        return None
    
    if not isinstance(config, dict):
        raise ValueError("generation_config must be a dictionary")
    
    # 验证 temperature (0-2)
    if "temperature" in config:
        temp = config["temperature"]
        if not isinstance(temp, (int, float)):
            raise ValueError("temperature must be a number")
        if not 0 <= temp <= 2:
            raise ValueError("temperature must be between 0 and 2")
    
    # 验证 max_output_tokens (正整数)
    if "max_output_tokens" in config:
        max_tokens = config["max_output_tokens"]
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
    
    # 验证 thinking_level (枚举值)
    if "thinking_level" in config:
        thinking_level = config["thinking_level"]
        valid_levels = ["minimal", "low", "medium", "high"]
        if thinking_level not in valid_levels:
            raise ValueError(f"thinking_level must be one of: {', '.join(valid_levels)}")
    
    # 验证 top_p (0-1)
    if "top_p" in config:
        top_p = config["top_p"]
        if not isinstance(top_p, (int, float)):
            raise ValueError("top_p must be a number")
        if not 0 <= top_p <= 1:
            raise ValueError("top_p must be between 0 and 1")
    
    # 验证 top_k (正整数)
    if "top_k" in config:
        top_k = config["top_k"]
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
    
    logger.debug(f"generation_config validated: {config}")
    return config


class InteractionsService:
    """
    Interactions API 核心服务
    
    提供统一的接口用于创建、查询、删除交互，支持：
    - 简单文本交互
    - 多轮对话（服务端状态管理）
    - 工具调用（Function Calling、Built-in Tools、Remote MCP）
    - 流式响应
    - 后台执行
    """
    
    def __init__(self, api_key: str):
        """
        初始化服务
        
        Args:
            api_key: Google GenAI API Key
            
        Raises:
            ValueError: API Key 无效或为空
            ConnectionError: 无法连接到 GenAI 服务
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API Key must be a non-empty string")
        
        try:
            # 初始化 GenAI Client
            self.client = genai.Client(api_key=api_key)
            logger.info("GenAI Client initialized successfully")
            
            # 初始化 StateManager（状态管理器）
            self.state_manager = StateManager()
            logger.info("StateManager initialized successfully")
            
            # 初始化 ToolOrchestrator（工具编排器）
            self.tool_orchestrator = ToolOrchestrator()
            logger.info("ToolOrchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize InteractionsService: {e}")
            raise ConnectionError(f"Failed to connect to GenAI service: {e}")
    
    async def create_interaction(
        self,
        model: Optional[str] = None,
        agent: Optional[str] = None,
        input: Union[str, List[Content]] = None,
        previous_interaction_id: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        stream: bool = False,
        background: bool = False,
        generation_config: Optional[GenerationConfig] = None,
        agent_config: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        response_format: Optional[dict] = None,
        store: bool = True,
        **kwargs
    ) -> Any:
        """
        创建新的交互
        
        Args:
            model: 模型 ID (与 agent 二选一)
            agent: 代理 ID (与 model 二选一)
            input: 用户输入 (文本或 Content 数组)
            previous_interaction_id: 上一个交互的 ID
            tools: 工具列表
            stream: 是否流式响应
            background: 是否后台执行
            generation_config: 生成配置 (仅用于 model，不能与 agent 同时使用)
            agent_config: 代理配置 (仅用于 agent，不能与 model 同时使用)
            system_instruction: 系统指令
            response_format: 结构化输出格式
            store: 是否存储交互
            
        Returns:
            Interaction 对象（google.genai SDK 返回的动态对象）
            
        Raises:
            ValueError: 参数验证失败
            HTTPException: API 调用失败
        """
        try:
            # 1. 参数验证
            if not model and not agent:
                raise ValueError("Must provide either model or agent")
            if model and agent:
                raise ValueError("Cannot provide both model and agent")
            if background and not agent:
                raise ValueError("background=True requires agent")
            if not store and previous_interaction_id:
                raise ValueError("store=False cannot use previous_interaction_id")
            
            # 验证 generation_config 和 agent_config 的互斥性
            if agent and generation_config:
                raise ValueError("Cannot use generation_config with agent. Use agent_config instead.")
            if model and agent_config:
                raise ValueError("Cannot use agent_config with model. Use generation_config instead.")
            
            # 验证 generation_config
            if generation_config:
                generation_config = validate_generation_config(generation_config)
            
            # 记录工具使用情况
            if tools:
                tool_types = []
                for tool in tools:
                    if isinstance(tool, dict) and 'type' in tool:
                        tool_types.append(tool['type'])
                    elif hasattr(tool, 'type'):
                        tool_types.append(tool.type)
                logger.info(f"Tools provided: {', '.join(tool_types)}")
            
            logger.info(f"Creating interaction with model={model}, agent={agent}, previous_id={previous_interaction_id}")
            
            # 2. 上下文加载（如果有 previous_interaction_id）
            context_messages = []
            if previous_interaction_id:
                # 从 StateManager 构建完整的对话链
                conversation_chain = await self.state_manager.build_conversation_chain(
                    previous_interaction_id
                )
                
                # 合并所有历史交互的输入和输出
                for interaction_data in conversation_chain:
                    # 添加历史输入
                    if interaction_data.get("input"):
                        context_messages.extend(interaction_data["input"])
                    # 添加历史输出
                    if interaction_data.get("outputs"):
                        context_messages.extend(interaction_data["outputs"])
                
                logger.info(f"Loaded context with {len(conversation_chain)} interactions, {len(context_messages)} messages")
            
            # 3. 准备输入
            if isinstance(input, str):
                # 对于字符串输入，直接传递给 SDK（SDK 会自动转换）
                input_messages = input
            else:
                input_messages = input
            
            # 如果有上下文，需要特殊处理
            if context_messages:
                # 如果有上下文，input 必须是列表格式
                if isinstance(input_messages, str):
                    # 将字符串转换为 Content 格式
                    input_messages = [Content(parts=[Part(text=input_messages)], role="user")]
                
                # 合并上下文和新输入
                all_messages = context_messages + input_messages
            else:
                # 没有上下文，直接使用原始输入
                all_messages = input_messages
            
            # 4. 调用 GenAI SDK
            # 根据是否使用 agent 来决定传递哪个配置参数
            if agent:
                # 构建参数字典，只包含非 None 的参数
                create_params = {
                    "agent": agent,
                    "input": all_messages,
                    "stream": stream,
                    "background": background,
                }
                
                # 只在非 None 且非空时添加可选参数
                if tools is not None:
                    create_params["tools"] = tools
                if agent_config is not None and agent_config:  # 确保不是空字典
                    create_params["agent_config"] = agent_config
                if system_instruction is not None:
                    create_params["system_instruction"] = system_instruction
                if response_format is not None:
                    create_params["response_format"] = response_format
                
                # 添加额外的 kwargs
                create_params.update(kwargs)
                
                interaction = self.client.interactions.create(**create_params)
            else:
                # 构建参数字典，只包含非 None 的参数
                create_params = {
                    "model": model,
                    "input": all_messages,
                    "stream": stream,
                    "background": background,
                }
                
                # 只在非 None 时添加可选参数
                if tools is not None:
                    create_params["tools"] = tools
                if generation_config is not None:
                    create_params["generation_config"] = generation_config
                if system_instruction is not None:
                    create_params["system_instruction"] = system_instruction
                if response_format is not None:
                    create_params["response_format"] = response_format
                
                # 添加额外的 kwargs
                create_params.update(kwargs)
                
                interaction = self.client.interactions.create(**create_params)
            
            logger.info(f"Interaction created: {interaction.id}, status={interaction.status}")
            
            # 5. 保存交互（如果 store=True）
            if store:
                # 保存原始输入（不包含上下文）和 previous_interaction_id
                interaction.input = input_messages
                interaction.previous_interaction_id = previous_interaction_id
                await self.state_manager.save_interaction(interaction)
            
            return interaction
            
        except ValueError as e:
            logger.error(f"Parameter validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create interaction: {e}")
            raise handle_gemini_error(e)
    
    async def get_interaction(
        self,
        interaction_id: str
    ) -> Any:
        """
        获取交互状态
        
        Args:
            interaction_id: 交互 ID
            
        Returns:
            Interaction 对象（google.genai SDK 返回的动态对象）
            
        Raises:
            HTTPException: 交互不存在或获取失败
        """
        try:
            logger.info(f"Getting interaction: {interaction_id}")
            
            interaction = self.client.interactions.get(interaction_id)
            
            logger.info(f"Interaction retrieved: {interaction_id}, status={interaction.status}")
            
            return interaction
            
        except Exception as e:
            logger.error(f"Failed to get interaction {interaction_id}: {e}")
            raise handle_gemini_error(e)
    
    async def stream_interaction(
        self,
        interaction_id: str,
        last_event_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式获取交互
        
        Args:
            interaction_id: 交互 ID
            last_event_id: 上次事件 ID（用于断点续传）
            
        Yields:
            流式事件块
            
        Raises:
            HTTPException: 交互不存在或流式获取失败
        """
        import asyncio
        from queue import Queue
        from threading import Thread
        
        try:
            logger.info(f"Streaming interaction: {interaction_id}, last_event_id={last_event_id}")
            
            # 使用队列在线程和异步代码之间传递数据
            queue = Queue()
            
            def sync_stream_worker():
                """在独立线程中运行同步的流式代码"""
                try:
                    # 调用 GenAI SDK 的流式接口（同步）
                    stream = self.client.interactions.get(
                        id=interaction_id,
                        stream=True,
                        last_event_id=last_event_id if last_event_id else None
                    )
                    
                    # 遍历流式事件（同步）
                    for chunk in stream:
                        event_data = {
                            "event_type": chunk.event_type,
                            "event_id": chunk.event_id if hasattr(chunk, 'event_id') and chunk.event_id else None
                        }
                        
                        # 处理不同类型的事件
                        if chunk.event_type == "interaction.start":
                            event_data["interaction"] = {
                                "id": chunk.interaction.id,
                                "status": chunk.interaction.status
                            }
                        
                        elif chunk.event_type == "content.delta":
                            # 根据官方文档，只有 text 和 thought_summary 两种类型
                            if hasattr(chunk, 'delta') and chunk.delta:
                                delta_type = chunk.delta.type if hasattr(chunk.delta, 'type') else None
                                
                                if delta_type == "text":
                                    event_data["delta"] = {
                                        "type": "text",
                                        "text": chunk.delta.text if hasattr(chunk.delta, 'text') else ""
                                    }
                                elif delta_type == "thought_summary":
                                    event_data["delta"] = {
                                        "type": "thought_summary",
                                        "content": {
                                            "text": chunk.delta.content.text if hasattr(chunk.delta, 'content') and hasattr(chunk.delta.content, 'text') else ""
                                        }
                                    }
                                elif delta_type == "thought":
                                    # Interactions API 也支持 thought 类型
                                    event_data["delta"] = {
                                        "type": "thought",
                                        "thought": chunk.delta.thought if hasattr(chunk.delta, 'thought') else ""
                                    }
                                else:
                                    # 未知类型，记录警告并尝试保留原始数据
                                    logger.warning(f"[SSE] Unknown delta type: {delta_type}")
                                    event_data["delta"] = {
                                        "type": str(delta_type),
                                        "raw_data": str(chunk.delta)
                                    }
                            else:
                                # content.delta 事件但没有 delta 对象
                                logger.warning(f"[SSE] content.delta event without delta object")
                        
                        elif chunk.event_type == "interaction.complete":
                            event_data["interaction"] = {
                                "id": chunk.interaction.id,
                                "status": "completed"
                            }
                            if hasattr(chunk.interaction, 'usage') and chunk.interaction.usage:
                                event_data["usage"] = chunk.interaction.usage.__dict__
                        
                        # 将事件放入队列
                        queue.put(("data", event_data))
                        
                        # 如果是完成事件，停止流式传输
                        if chunk.event_type == "interaction.complete":
                            break
                    
                    logger.info(f"Stream completed for interaction: {interaction_id}")
                    # 发送完成信号
                    queue.put(("done", None))
                    
                except Exception as e:
                    logger.error(f"Failed to stream interaction {interaction_id}: {e}")
                    # 发送错误事件
                    queue.put(("data", {
                        "event_type": "error",
                        "error": str(e)
                    }))
                    queue.put(("done", None))
            
            # 启动工作线程
            thread = Thread(target=sync_stream_worker, daemon=True)
            thread.start()
            
            # 从队列中读取事件并 yield
            while True:
                # 使用 asyncio.to_thread 避免阻塞事件循环
                msg_type, data = await asyncio.to_thread(queue.get)
                
                if msg_type == "done":
                    break
                elif msg_type == "data":
                    yield data
            
        except Exception as e:
            logger.error(f"Failed to stream interaction {interaction_id}: {e}")
            # 返回错误事件
            yield {
                "event_type": "error",
                "error": str(e)
            }
    
    async def delete_interaction(
        self,
        interaction_id: str
    ) -> None:
        """
        删除交互
        
        Args:
            interaction_id: 交互 ID
            
        Raises:
            HTTPException: 删除失败
        """
        try:
            logger.info(f"Deleting interaction: {interaction_id}")
            
            # 从 GenAI 服务删除
            self.client.interactions.delete(interaction_id)
            
            # 从本地存储删除
            await self.state_manager.delete_interaction(interaction_id)
            
            logger.info(f"Interaction deleted: {interaction_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete interaction {interaction_id}: {e}")
            raise handle_gemini_error(e)
