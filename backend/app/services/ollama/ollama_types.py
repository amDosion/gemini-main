"""
Ollama Provider数据类型定义

定义Ollama专用的数据类型，用于：
- 模型能力检测
- 模型详细信息缓存
- API模式切换
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class OllamaAPIMode(Enum):
    """Ollama API模式枚举"""
    NATIVE = "native"  # 原生Ollama API (/api/*)
    OPENAI_COMPAT = "openai_compat"  # OpenAI兼容API (/v1/*)


@dataclass
class OllamaModelCapabilities:
    """
    Ollama模型能力数据类

    从/api/show endpoint动态获取模型能力,避免硬编码
    支持TTL缓存，避免重复API调用
    """
    # 核心能力标志
    supports_tools: bool = False  # 支持工具调用（function calling）
    supports_vision: bool = False  # 支持视觉输入（图片理解）
    supports_structured_output: bool = False  # 支持结构化JSON输出
    supports_thinking: bool = False  # 支持推理思考模式（reasoning）

    # 模型配置
    context_length: int = 4096  # 上下文窗口长度（tokens）
    family: Optional[str] = None  # 模型系列（llama, qwen, gemma等）
    parameter_size: Optional[str] = None  # 参数量（7B, 13B, 70B等）
    quantization: Optional[str] = None  # 量化方式（Q4_K_M, Q5_K_S等）

    # 缓存元数据
    detected_at: Optional[datetime] = None  # 检测时间戳
    ttl_seconds: int = 3600  # 缓存有效期（默认1小时）

    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        if not self.detected_at:
            return True
        elapsed = (datetime.now() - self.detected_at).total_seconds()
        return elapsed > self.ttl_seconds


@dataclass
class OllamaModelInfo:
    """
    Ollama模型详细信息

    完整的模型元数据,从/api/show响应解析
    """
    # 基础信息
    name: str  # 模型名称（如llama3.2:latest）
    size: int = 0  # 模型大小（字节）
    modified_at: Optional[str] = None  # 修改时间

    # 模型详情
    modelfile: Optional[str] = None  # Modelfile内容
    parameters: Optional[str] = None  # 模型参数配置
    template: Optional[str] = None  # 提示词模板

    # model_info字段（嵌套字典）
    model_info: Dict[str, Any] = field(default_factory=dict)

    # 能力信息（解析后）
    capabilities: Optional[OllamaModelCapabilities] = None

    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> "OllamaModelInfo":
        """
        从/api/show API响应创建ModelInfo实例

        Args:
            response_data: API响应JSON

        Returns:
            OllamaModelInfo实例，包含解析后的能力信息
        """
        # 提取基础信息
        name = response_data.get("model", "unknown")
        size = response_data.get("size", 0)
        modified_at = response_data.get("modified_at")
        modelfile = response_data.get("modelfile")
        parameters = response_data.get("parameters")
        template = response_data.get("template")
        model_info = response_data.get("model_info", {})

        # 解析能力信息
        capabilities = cls._parse_capabilities(response_data, model_info)

        return cls(
            name=name,
            size=size,
            modified_at=modified_at,
            modelfile=modelfile,
            parameters=parameters,
            template=template,
            model_info=model_info,
            capabilities=capabilities
        )

    @staticmethod
    def _parse_capabilities(
        response_data: Dict[str, Any],
        model_info: Dict[str, Any]
    ) -> OllamaModelCapabilities:
        """
        从API响应解析模型能力

        Args:
            response_data: 完整API响应
            model_info: model_info字段

        Returns:
            OllamaModelCapabilities实例
        """
        # 从capabilities数组检测能力
        capabilities_array = response_data.get("capabilities", [])

        supports_tools = "tools" in capabilities_array
        supports_vision = "vision" in capabilities_array
        supports_structured_output = "structured_output" in capabilities_array
        supports_thinking = "thinking" in capabilities_array

        # 从model_info提取配置
        family = model_info.get("general.architecture")
        parameter_size = model_info.get("general.parameter_count")
        quantization = model_info.get("general.quantization_version")

        # context_length的多种可能字段名
        context_length = (
            model_info.get("llama.context_length") or
            model_info.get("qwen2.context_length") or
            model_info.get("gemma2.context_length") or
            model_info.get("mistral.context_length") or
            4096  # 默认值
        )

        # 创建能力对象
        return OllamaModelCapabilities(
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            supports_structured_output=supports_structured_output,
            supports_thinking=supports_thinking,
            context_length=int(context_length) if context_length else 4096,
            family=family,
            parameter_size=parameter_size,
            quantization=quantization,
            detected_at=datetime.now(),
            ttl_seconds=3600  # 1小时缓存
        )


@dataclass
class OllamaToolCallState:
    """
    工具调用流式聚合状态

    用于在流式响应中聚合tool_calls的碎片化chunks
    采用状态机模式，按index独立跟踪每个工具调用
    """
    # 工具调用列表（按index索引）
    tool_calls: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # 聚合状态标志
    is_complete: bool = False  # 所有工具调用是否完整
    last_updated: datetime = field(default_factory=datetime.now)

    def update_chunk(self, tool_call_chunk: Dict[str, Any]) -> None:
        """
        更新工具调用chunk

        Args:
            tool_call_chunk: 单个tool call的增量数据
                {
                    "index": 0,
                    "id": "call_abc",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "Beijing"}'  # 可能分片
                    }
                }
        """
        index = tool_call_chunk.get("index", 0)

        # 初始化该index的工具调用
        if index not in self.tool_calls:
            self.tool_calls[index] = {
                "id": tool_call_chunk.get("id", ""),
                "type": tool_call_chunk.get("type", "function"),
                "function": {
                    "name": "",
                    "arguments": ""
                }
            }

        # 聚合增量数据
        tool_call = self.tool_calls[index]

        # 更新id（通常只在第一个chunk出现）
        if tool_call_chunk.get("id"):
            tool_call["id"] = tool_call_chunk["id"]

        # 更新function信息（追加arguments）
        if "function" in tool_call_chunk:
            func_chunk = tool_call_chunk["function"]
            if func_chunk.get("name"):
                tool_call["function"]["name"] = func_chunk["name"]
            if func_chunk.get("arguments"):
                tool_call["function"]["arguments"] += func_chunk["arguments"]

        self.last_updated = datetime.now()

    def get_completed_calls(self) -> List[Dict[str, Any]]:
        """
        获取已完成的工具调用列表

        验证arguments是否为完整的JSON,过滤不完整的调用

        Returns:
            完整的tool_calls列表
        """
        import json

        completed = []
        for index in sorted(self.tool_calls.keys()):
            call = self.tool_calls[index]
            # 验证JSON完整性
            try:
                json.loads(call["function"]["arguments"])
                completed.append(call)
            except (json.JSONDecodeError, KeyError):
                # 不完整的调用，跳过
                continue

        return completed

    def is_timeout(self, timeout_seconds: int = 120) -> bool:
        """检查是否超时（防止状态泄漏）"""
        elapsed = (datetime.now() - self.last_updated).total_seconds()
        return elapsed > timeout_seconds
