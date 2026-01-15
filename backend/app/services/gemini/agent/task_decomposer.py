"""
Smart Task Decomposer - 智能任务分解器

使用 LLM 将复杂任务分解为可执行的子任务，每个子任务包含：
- 描述
- 所需能力
- 建议的代理 ID
- 依赖关系
"""

import logging
import json
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ..google_service import GoogleService

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """
    子任务数据类
    
    Attributes:
        id: 子任务 ID（自动生成）
        description: 任务描述
        required_capabilities: 所需能力列表
        suggested_agent_id: 建议的代理 ID（可选）
        dependencies: 依赖的其他子任务 ID 列表
        priority: 优先级（1-10，数字越大优先级越高）
    """
    description: str
    required_capabilities: List[str] = field(default_factory=list)
    suggested_agent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    priority: int = 5
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "description": self.description,
            "required_capabilities": self.required_capabilities,
            "suggested_agent_id": self.suggested_agent_id,
            "dependencies": self.dependencies,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubTask":
        """从字典创建"""
        return cls(
            id=data.get("id"),
            description=data.get("description", ""),
            required_capabilities=data.get("required_capabilities", []),
            suggested_agent_id=data.get("suggested_agent_id"),
            dependencies=data.get("dependencies", []),
            priority=data.get("priority", 5)
        )


class SmartTaskDecomposer:
    """
    智能任务分解器
    
    使用 LLM 分析任务并分解为可执行的子任务
    """
    
    def __init__(
        self,
        google_service: GoogleService,
        model: str = "gemini-2.0-flash-exp"
    ):
        """
        初始化任务分解器
        
        Args:
            google_service: GoogleService 实例
            model: 使用的模型（默认：gemini-2.0-flash-exp）
        """
        self.google_service = google_service
        self.model = model
        logger.info(f"[SmartTaskDecomposer] Initialized with model: {model}")
    
    async def decompose_task(
        self,
        task: str,
        available_agents: List[Dict[str, Any]],
        max_subtasks: int = 10
    ) -> List[SubTask]:
        """
        使用 LLM 分析任务并分解为子任务
        
        Args:
            task: 任务描述
            available_agents: 可用代理列表（每个包含 id, name, capabilities 等）
            max_subtasks: 最大子任务数量（默认：10）
            
        Returns:
            List[SubTask]: 子任务列表
            
        Raises:
            ValueError: 如果任务描述为空
            RuntimeError: 如果 LLM 调用失败或解析失败
        """
        if not task or not task.strip():
            raise ValueError("Task description cannot be empty")
        
        if not available_agents:
            logger.warning("[SmartTaskDecomposer] No available agents provided")
        
        try:
            # 构建提示词
            prompt = self._build_decomposition_prompt(
                task=task,
                available_agents=available_agents,
                max_subtasks=max_subtasks
            )
            
            # 调用 LLM
            logger.info(f"[SmartTaskDecomposer] Decomposing task: {task[:50]}...")
            response = await self._call_llm(prompt)
            
            # 解析响应
            subtasks = self._parse_subtasks(response, max_subtasks)
            
            logger.info(f"[SmartTaskDecomposer] Decomposed into {len(subtasks)} subtasks")
            return subtasks
            
        except json.JSONDecodeError as e:
            logger.error(f"[SmartTaskDecomposer] JSON parsing error: {e}")
            raise RuntimeError(f"Failed to parse LLM response as JSON: {e}")
        except Exception as e:
            logger.error(f"[SmartTaskDecomposer] Error decomposing task: {e}", exc_info=True)
            raise RuntimeError(f"Failed to decompose task: {e}")
    
    def _build_decomposition_prompt(
        self,
        task: str,
        available_agents: List[Dict[str, Any]],
        max_subtasks: int
    ) -> str:
        """
        构建任务分解提示词
        
        Args:
            task: 任务描述
            available_agents: 可用代理列表
            max_subtasks: 最大子任务数量
            
        Returns:
            提示词字符串
        """
        agents_info = self._format_agents(available_agents)
        
        prompt = f"""你是一个任务分解专家。请分析以下任务，并将其分解为可执行的子任务。

任务描述：
{task}

可用代理信息：
{agents_info}

请将任务分解为最多 {max_subtasks} 个子任务，每个子任务应该：
1. 有清晰的描述
2. 明确所需的能力
3. 建议合适的代理（从可用代理中选择）
4. 说明依赖关系（如果有）

请以 JSON 格式返回，格式如下：
{{
  "subtasks": [
    {{
      "id": "subtask_1",
      "description": "子任务描述",
      "required_capabilities": ["能力1", "能力2"],
      "suggested_agent_id": "agent_id（可选）",
      "dependencies": ["subtask_id1", "subtask_id2"],
      "priority": 5
    }}
  ]
}}

注意：
- 每个子任务必须有唯一的 id
- dependencies 是依赖的其他子任务的 id 列表
- priority 是优先级（1-10，数字越大优先级越高）
- 如果某个子任务不依赖其他任务，dependencies 为空数组
- 确保没有循环依赖
"""
        return prompt
    
    def _format_agents(self, agents: List[Dict[str, Any]]) -> str:
        """
        格式化代理信息为字符串
        
        Args:
            agents: 代理列表
            
        Returns:
            格式化的代理信息字符串
        """
        if not agents:
            return "无可用代理"
        
        formatted = []
        for agent in agents:
            agent_id = agent.get("id", "unknown")
            name = agent.get("name", "Unknown Agent")
            capabilities = agent.get("capabilities", [])
            agent_type = agent.get("agent_type", "unknown")
            
            formatted.append(
                f"- ID: {agent_id}, 名称: {name}, 类型: {agent_type}, "
                f"能力: {', '.join(capabilities) if capabilities else '无'}"
            )
        
        return "\n".join(formatted)
    
    async def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM 进行任务分解
        
        Args:
            prompt: 提示词
            
        Returns:
            LLM 响应文本
        """
        try:
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # 调用 GoogleService 的 chat 方法
            response = await self.google_service.chat(
                messages=messages,
                model=self.model,
                temperature=0.3,  # 较低温度以获得更稳定的输出
                response_format="json"  # 如果支持，请求 JSON 格式
            )
            
            # 提取响应文本
            if isinstance(response, dict):
                # 处理不同的响应格式
                if "text" in response:
                    text = response["text"]
                elif "content" in response:
                    text = response["content"]
                elif "message" in response and "content" in response["message"]:
                    text = response["message"]["content"]
                else:
                    # 尝试从 choices 或其他字段提取
                    text = str(response)
            else:
                text = str(response)
            
            # 尝试提取 JSON（如果响应包含代码块）
            text = self._extract_json_from_response(text)
            
            return text
            
        except Exception as e:
            logger.error(f"[SmartTaskDecomposer] LLM call failed: {e}", exc_info=True)
            raise RuntimeError(f"LLM call failed: {e}")
    
    def _extract_json_from_response(self, response: str) -> str:
        """
        从响应中提取 JSON（处理代码块等格式）
        
        Args:
            response: LLM 响应文本
            
        Returns:
            提取的 JSON 字符串
        """
        # 尝试查找 JSON 代码块
        import re
        
        # 匹配 ```json ... ``` 或 ``` ... ```
        json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_block_pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        
        # 尝试直接查找 JSON 对象
        json_obj_pattern = r'\{.*\}'
        match = re.search(json_obj_pattern, response, re.DOTALL)
        if match:
            return match.group(0)
        
        # 如果没有找到，返回原始响应
        return response
    
    def _parse_subtasks(self, response: str, max_subtasks: int) -> List[SubTask]:
        """
        解析 LLM 响应为子任务列表
        
        Args:
            response: LLM 响应文本
            max_subtasks: 最大子任务数量
            
        Returns:
            子任务列表
            
        Raises:
            ValueError: 如果 JSON 格式无效
        """
        try:
            # 解析 JSON
            data = json.loads(response)
            
            # 验证结构
            if "subtasks" not in data:
                raise ValueError("Response missing 'subtasks' field")
            
            subtasks_data = data["subtasks"]
            if not isinstance(subtasks_data, list):
                raise ValueError("'subtasks' must be a list")
            
            # 限制子任务数量
            if len(subtasks_data) > max_subtasks:
                logger.warning(
                    f"[SmartTaskDecomposer] Received {len(subtasks_data)} subtasks, "
                    f"limiting to {max_subtasks}"
                )
                subtasks_data = subtasks_data[:max_subtasks]
            
            # 转换为 SubTask 对象
            subtasks = []
            for i, subtask_data in enumerate(subtasks_data):
                try:
                    # 如果没有 id，自动生成
                    if "id" not in subtask_data or not subtask_data["id"]:
                        subtask_data["id"] = f"subtask_{i+1}"
                    
                    subtask = SubTask.from_dict(subtask_data)
                    subtasks.append(subtask)
                except Exception as e:
                    logger.warning(
                        f"[SmartTaskDecomposer] Failed to parse subtask {i+1}: {e}, "
                        f"skipping..."
                    )
                    continue
            
            if not subtasks:
                raise ValueError("No valid subtasks found in response")
            
            # 验证依赖关系（检查循环依赖）
            self._validate_dependencies(subtasks)
            
            return subtasks
            
        except json.JSONDecodeError as e:
            logger.error(f"[SmartTaskDecomposer] JSON decode error: {e}")
            logger.error(f"[SmartTaskDecomposer] Response text: {response[:500]}")
            raise ValueError(f"Invalid JSON format: {e}")
    
    def _validate_dependencies(self, subtasks: List[SubTask]) -> None:
        """
        验证子任务依赖关系（检查循环依赖）
        
        Args:
            subtasks: 子任务列表
            
        Raises:
            ValueError: 如果发现循环依赖
        """
        # 构建依赖图
        task_ids = {task.id for task in subtasks if task.id}
        
        # 检查每个任务的依赖是否有效
        for task in subtasks:
            if not task.id:
                continue
            
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    logger.warning(
                        f"[SmartTaskDecomposer] Subtask {task.id} depends on "
                        f"unknown subtask {dep_id}, ignoring..."
                    )
                    task.dependencies.remove(dep_id)
        
        # 检查循环依赖（使用 DFS）
        visited = set()
        rec_stack = set()
        
        def has_cycle(task_id: str) -> bool:
            if task_id in rec_stack:
                return True
            if task_id in visited:
                return False
            
            visited.add(task_id)
            rec_stack.add(task_id)
            
            # 找到对应的任务
            task = next((t for t in subtasks if t.id == task_id), None)
            if task:
                for dep_id in task.dependencies:
                    if has_cycle(dep_id):
                        return True
            
            rec_stack.remove(task_id)
            return False
        
        for task in subtasks:
            if task.id and task.id not in visited:
                if has_cycle(task.id):
                    raise ValueError(f"Circular dependency detected involving subtask {task.id}")
