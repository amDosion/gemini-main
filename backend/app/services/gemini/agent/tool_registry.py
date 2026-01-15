"""
Tool Registry - 工具注册表

提供：
- 工具注册和发现
- MCP 工具集成
- Google Search 工具
- 工作流工具（图像编辑、Excel 分析）
- 工具格式转换
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """
    工具基类
    
    Attributes:
        name: 工具名称
        description: 工具描述
        parameters: 参数 Schema（JSON Schema 格式）
        category: 工具分类（builtin/mcp/custom）
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    category: str = "custom"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "category": self.category
        }
    
    def to_gemini_format(self) -> Dict[str, Any]:
        """转换为 Gemini Function Calling 格式"""
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }]
        }


class ToolExecutor(ABC):
    """工具执行器接口"""
    
    @abstractmethod
    async def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            执行结果
        """
        pass


class BuiltinToolExecutor(ToolExecutor):
    """内置工具执行器"""
    
    def __init__(self):
        self._executors: Dict[str, Callable] = {}
    
    def register(self, name: str, executor: Callable):
        """注册执行器"""
        self._executors[name] = executor
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        executor = self._executors.get(name)
        if not executor:
            raise ValueError(f"Tool executor not found: {name}")
        
        if callable(executor):
            # 如果是异步函数
            import inspect
            if inspect.iscoroutinefunction(executor):
                return await executor(**arguments)
            else:
                return executor(**arguments)
        
        raise ValueError(f"Invalid executor for tool: {name}")


class MCPToolExecutor(ToolExecutor):
    """MCP 工具执行器"""
    
    def __init__(self, mcp_manager: Any, session_id: str):
        """
        初始化 MCP 工具执行器
        
        Args:
            mcp_manager: MCPManager 实例
            session_id: MCP 会话 ID
        """
        self.mcp_manager = mcp_manager
        self.session_id = session_id
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行 MCP 工具"""
        try:
            result = await self.mcp_manager.call_tool(
                session_id=self.session_id,
                tool_name=name,
                arguments=arguments
            )
            
            if result.is_error:
                return {
                    "success": False,
                    "error": result.error
                }
            
            return {
                "success": True,
                "result": result.result
            }
        except Exception as e:
            logger.error(f"[MCPToolExecutor] Error executing tool {name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# 延迟导入 MCPManager 以避免循环依赖
def _get_mcp_manager():
    """获取 MCPManager 实例（延迟导入）"""
    try:
        from ...mcp_manager import get_mcp_manager
        return get_mcp_manager()
    except ImportError:
        logger.warning("[ToolRegistry] MCPManager not available")
        return None


class ToolRegistry:
    """
    工具注册表
    
    管理所有可用工具：
    - 内置工具（Google Search 等）
    - MCP 工具（从 MCPManager 加载）
    - 自定义工具
    """
    
    def __init__(self, mcp_manager: Optional[Any] = None):
        """
        初始化工具注册表
        
        Args:
            mcp_manager: MCPManager 实例（可选，如果不提供则尝试自动获取）
        """
        self.tools: Dict[str, Tool] = {}
        self.executors: Dict[str, ToolExecutor] = {}
        self.mcp_manager = mcp_manager or _get_mcp_manager()
        self.mcp_session_id: Optional[str] = None
        
        # 注册内置工具
        self._register_builtin_tools()
        
        logger.info(f"[ToolRegistry] Initialized (MCPManager: {'available' if self.mcp_manager else 'not available'})")
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        # Google Search 工具
        google_search_tool = Tool(
            name="google_search",
            description="使用 Google 搜索信息",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "返回结果数量（默认：10）",
                        "default": 10
                    }
                },
                "required": ["query"]
            },
            category="builtin"
        )
        self.register(google_search_tool, BuiltinToolExecutor())
        
        # 注册 Google Search 执行器
        builtin_executor = self.executors["google_search"]
        if isinstance(builtin_executor, BuiltinToolExecutor):
            builtin_executor.register("google_search", self._execute_google_search)
        
        # 图像编辑工具
        analyze_image_tool = Tool(
            name="analyze_image",
            description="使用 Gemini Vision 分析图像内容、风格、质量和编辑可行性",
            parameters={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "图像 URL 或 Base64 编码"
                    }
                },
                "required": ["image_url"]
            },
            category="builtin"
        )
        self.register(analyze_image_tool, BuiltinToolExecutor())
        
        edit_image_tool = Tool(
            name="edit_image_with_imagen",
            description="使用 Imagen 编辑图像",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "编辑提示"
                    },
                    "reference_image": {
                        "type": "string",
                        "description": "参考图像 URL 或 Base64"
                    },
                    "mask": {
                        "type": "string",
                        "description": "掩码图像（可选）"
                    },
                    "edit_mode": {
                        "type": "string",
                        "description": "编辑模式（inpainting, outpainting, background-edit等）",
                        "default": "inpainting"
                    }
                },
                "required": ["prompt", "reference_image"]
            },
            category="builtin"
        )
        self.register(edit_image_tool, BuiltinToolExecutor())
        
        # Excel 分析工具
        read_excel_tool = Tool(
            name="read_excel_file",
            description="读取 Excel 文件并理解数据结构",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Excel 文件路径"
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "工作表名称（可选）"
                    }
                },
                "required": ["file_path"]
            },
            category="builtin"
        )
        self.register(read_excel_tool, BuiltinToolExecutor())
        
        clean_dataframe_tool = Tool(
            name="clean_dataframe",
            description="清理和预处理数据框",
            parameters={
                "type": "object",
                "properties": {
                    "df_data": {
                        "type": "object",
                        "description": "数据框数据（字典格式）"
                    },
                    "cleaning_rules": {
                        "type": "object",
                        "description": "清理规则"
                    }
                },
                "required": ["df_data", "cleaning_rules"]
            },
            category="builtin"
        )
        self.register(clean_dataframe_tool, BuiltinToolExecutor())
        
        analyze_dataframe_tool = Tool(
            name="analyze_dataframe",
            description="分析数据框（统计、相关性、趋势等）",
            parameters={
                "type": "object",
                "properties": {
                    "df_data": {
                        "type": "object",
                        "description": "数据框数据（字典格式）"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "分析类型（comprehensive, statistics, correlation, trends）",
                        "default": "comprehensive"
                    }
                },
                "required": ["df_data"]
            },
            category="builtin"
        )
        self.register(analyze_dataframe_tool, BuiltinToolExecutor())
        
        generate_chart_tool = Tool(
            name="generate_chart",
            description="生成数据可视化图表",
            parameters={
                "type": "object",
                "properties": {
                    "df_data": {
                        "type": "object",
                        "description": "数据框数据（字典格式）"
                    },
                    "chart_type": {
                        "type": "string",
                        "description": "图表类型（bar, line, scatter, histogram, pie）"
                    },
                    "x_column": {
                        "type": "string",
                        "description": "X 轴列名"
                    },
                    "y_column": {
                        "type": "string",
                        "description": "Y 轴列名（可选）"
                    }
                },
                "required": ["df_data", "chart_type", "x_column"]
            },
            category="builtin"
        )
        self.register(generate_chart_tool, BuiltinToolExecutor())
        
        # 注册工具执行器（需要传入 google_service）
        # 注意：这些工具需要 google_service，将在使用时动态注册
    
    def register(self, tool: Tool, executor: Optional[ToolExecutor] = None):
        """
        注册工具
        
        Args:
            tool: 工具对象
            executor: 工具执行器（可选，如果不提供则使用默认执行器）
        """
        if tool.name in self.tools:
            logger.warning(f"[ToolRegistry] Tool {tool.name} already registered, overwriting...")
        
        self.tools[tool.name] = tool
        
        if executor:
            self.executors[tool.name] = executor
        elif tool.category == "builtin":
            # 内置工具使用 BuiltinToolExecutor
            if tool.name not in self.executors:
                self.executors[tool.name] = BuiltinToolExecutor()
        
        logger.info(f"[ToolRegistry] Registered tool: {tool.name} (category: {tool.category})")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具对象，如果不存在则返回 None
        """
        return self.tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[Tool]:
        """
        列出工具
        
        Args:
            category: 工具分类（可选，用于过滤）
            
        Returns:
            工具列表
        """
        if category:
            return [tool for tool in self.tools.values() if tool.category == category]
        return list(self.tools.values())
    
    def search_tools(self, query: str) -> List[Tool]:
        """
        搜索工具（按名称或描述）
        
        Args:
            query: 搜索查询
            
        Returns:
            匹配的工具列表
        """
        query_lower = query.lower()
        matches = []
        
        for tool in self.tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower()):
                matches.append(tool)
        
        return matches
    
    async def load_mcp_tools(self, session_id: str) -> List[Tool]:
        """
        从 MCP 管理器加载工具
        
        Args:
            session_id: MCP 会话 ID
            
        Returns:
            加载的 MCP 工具列表
        """
        if not self.mcp_manager:
            logger.warning("[ToolRegistry] MCPManager not available, skipping MCP tools")
            return []
        
        try:
            # 获取 MCP 工具列表
            mcp_tools = await self.mcp_manager.list_tools(session_id)
            
            # 转换为 Tool 对象
            tools = []
            for mcp_tool in mcp_tools:
                tool = Tool(
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    parameters=mcp_tool.input_schema,
                    category="mcp"
                )
                tools.append(tool)
                
                # 注册工具和执行器
                self.register(tool, MCPToolExecutor(self.mcp_manager, session_id))
            
            self.mcp_session_id = session_id
            logger.info(f"[ToolRegistry] Loaded {len(tools)} MCP tools from session {session_id}")
            return tools
            
        except Exception as e:
            logger.error(f"[ToolRegistry] Failed to load MCP tools: {e}", exc_info=True)
            return []
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            执行结果
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        executor = self.executors.get(name)
        if not executor:
            raise ValueError(f"Executor not found for tool: {name}")
        
        try:
            # 检查执行器是否有 execute 方法（BuiltinToolExecutor）
            if isinstance(executor, BuiltinToolExecutor):
                # BuiltinToolExecutor 的 execute 方法需要工具名称和参数
                result = await executor.execute(name, arguments)
            else:
                # 其他执行器可能有不同的接口
                result = await executor.execute(name, arguments)
            
            logger.info(f"[ToolRegistry] Tool {name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"[ToolRegistry] Tool execution failed: {name}, error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_google_search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        执行 Google Search
        
        Args:
            query: 搜索查询
            num_results: 返回结果数量
            
        Returns:
            搜索结果
        """
        # TODO: 实现实际的 Google Search API 调用
        # 可以使用 Google Custom Search API 或其他搜索服务
        logger.info(f"[ToolRegistry] Google Search: {query} (num_results={num_results})")
        
        # 占位实现
        return {
            "success": True,
            "results": [
                {
                    "title": f"搜索结果 {i+1}",
                    "url": f"https://example.com/result{i+1}",
                    "snippet": f"关于 '{query}' 的搜索结果摘要 {i+1}"
                }
                for i in range(min(num_results, 5))
            ],
            "query": query
        }
    
    def register_workflow_tools(self, google_service: Optional[Any] = None):
        """
        注册工作流工具（需要 google_service）
        
        Args:
            google_service: GoogleService 实例（用于图像分析和编辑）
        """
        if not google_service:
            logger.warning("[ToolRegistry] google_service not provided, workflow tools not registered")
            return
        
        # 注册图像工具执行器（异步函数需要特殊处理）
        from .tools.image_tools import analyze_image, edit_image_with_imagen
        
        if "analyze_image" in self.tools:
            executor = self.executors.get("analyze_image")
            if isinstance(executor, BuiltinToolExecutor):
                # 创建异步包装器
                async def analyze_image_wrapper(image_url: str, model: str = "gemini-2.0-flash-exp"):
                    return await analyze_image(image_url, google_service, model)
                executor.register("analyze_image", analyze_image_wrapper)
        
        if "edit_image_with_imagen" in self.tools:
            executor = self.executors.get("edit_image_with_imagen")
            if isinstance(executor, BuiltinToolExecutor):
                async def edit_image_wrapper(
                    prompt: str,
                    reference_image: str,
                    mask: Optional[str] = None,
                    edit_mode: str = "inpainting",
                    model: str = "imagen-3.0-generate-001"
                ):
                    return await edit_image_with_imagen(
                        prompt, reference_image, google_service, mask, edit_mode, model
                    )
                executor.register("edit_image_with_imagen", edit_image_wrapper)
        
        # 注册 Excel 工具执行器
        from .tools.excel_tools import read_excel_file, clean_dataframe, analyze_dataframe, generate_chart
        
        if "read_excel_file" in self.tools:
            executor = self.executors.get("read_excel_file")
            if isinstance(executor, BuiltinToolExecutor):
                async def read_excel_wrapper(file_path: str, sheet_name: Optional[str] = None):
                    return await read_excel_file(file_path, sheet_name)
                executor.register("read_excel_file", read_excel_wrapper)
        
        if "clean_dataframe" in self.tools:
            executor = self.executors.get("clean_dataframe")
            if isinstance(executor, BuiltinToolExecutor):
                async def clean_dataframe_wrapper(df_data: Dict[str, Any], cleaning_rules: Dict[str, Any]):
                    return await clean_dataframe(df_data, cleaning_rules)
                executor.register("clean_dataframe", clean_dataframe_wrapper)
        
        if "analyze_dataframe" in self.tools:
            executor = self.executors.get("analyze_dataframe")
            if isinstance(executor, BuiltinToolExecutor):
                async def analyze_dataframe_wrapper(df_data: Dict[str, Any], analysis_type: str = "comprehensive"):
                    return await analyze_dataframe(df_data, analysis_type)
                executor.register("analyze_dataframe", analyze_dataframe_wrapper)
        
        if "generate_chart" in self.tools:
            executor = self.executors.get("generate_chart")
            if isinstance(executor, BuiltinToolExecutor):
                async def generate_chart_wrapper(
                    df_data: Dict[str, Any],
                    chart_type: str,
                    x_column: str,
                    y_column: Optional[str] = None,
                    title: Optional[str] = None
                ):
                    return await generate_chart(df_data, chart_type, x_column, y_column, title)
                executor.register("generate_chart", generate_chart_wrapper)
        
        logger.info("[ToolRegistry] Workflow tools registered")
    
    def to_gemini_tools(self) -> List[Dict[str, Any]]:
        """
        转换为 Gemini Function Calling 格式
        
        Returns:
            Gemini 工具列表
        """
        gemini_tools = []
        for tool in self.tools.values():
            gemini_tools.append(tool.to_gemini_format())
        return gemini_tools
    
    def get_tools_by_category(self, category: str) -> List[Tool]:
        """
        按分类获取工具
        
        Args:
            category: 工具分类
            
        Returns:
            工具列表
        """
        return [tool for tool in self.tools.values() if tool.category == category]
    
    def unregister(self, name: str) -> bool:
        """
        注销工具
        
        Args:
            name: 工具名称
            
        Returns:
            True 如果成功注销，False 如果工具不存在
        """
        if name in self.tools:
            del self.tools[name]
            if name in self.executors:
                del self.executors[name]
            logger.info(f"[ToolRegistry] Unregistered tool: {name}")
            return True
        return False
