"""
Tools Integration - 工具集成管理

提供工具注册、调用和管理功能
支持 Browser 工具（web_search, read_webpage, selenium_browse）
"""

import logging
import re
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)

# URL 检测正则表达式（使用共享工具中的实现）
def is_url(text: str) -> bool:
    """
    检测文本是否是 URL
    
    Args:
        text: 要检测的文本
        
    Returns:
        如果是 URL 返回 True，否则返回 False
    """
    if not text or not isinstance(text, str):
        return False
    
    text = text.strip()
    
    # 使用共享工具中的 URL 检测函数
    try:
        from ...gemini.shared.utils import is_url as shared_is_url
        return shared_is_url(text)
    except ImportError:
        # 如果导入失败，使用简单的检测
        # 检查是否以 http:// 或 https:// 开头
        if text.startswith(('http://', 'https://')):
            return True
        
        # 检查是否包含常见的 URL 特征
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        return bool(url_pattern.match(text))


class ToolManager:
    """工具管理器"""
    
    def __init__(self, tools: List[Dict[str, Any]]):
        """
        初始化工具管理器
        
        Args:
            tools: 工具配置列表
        """
        self.tools = tools
        self._registered_tools = {}
        self._register_tools()
        logger.info(f"[ToolManager] Initialized with {len(self.tools)} tools")
    
    def _register_tools(self):
        """注册工具"""
        for tool in self.tools:
            tool_type = tool.get('type')
            if tool_type == 'google_search':
                self._register_google_search()
            elif tool_type == 'file_search':
                self._register_file_search(tool.get('file_search_store_names', []))
            elif tool_type == 'code_execution':
                self._register_code_execution()
            elif tool_type == 'browser' or tool_type == 'enable_browser':
                # 注册 Browser 工具
                self._register_browser_tools()
            # 可以添加更多工具类型
        
        # 如果没有显式注册 Browser 工具，但检测到 URL，自动注册
        # 注意：这里无法直接访问 prompt，需要在外部调用时处理
    
    def _register_google_search(self):
        """注册 Google Search 工具"""
        self._registered_tools['google_search'] = {
            'name': 'google_search',
            'description': 'Search the web using Google Search',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'Search query'
                    }
                },
                'required': ['query']
            }
        }
    
    def _register_file_search(self, store_names: List[str]):
        """注册 File Search 工具"""
        if store_names:
            self._registered_tools['file_search'] = {
                'name': 'file_search',
                'description': 'Search in uploaded documents',
                'parameters': {
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
                },
                'store_names': store_names
            }
    
    def _register_code_execution(self):
        """注册 Code Execution 工具"""
        self._registered_tools['code_execution'] = {
            'name': 'code_execution',
            'description': 'Execute Python code',
            'parameters': {
                'type': 'object',
                'properties': {
                    'code': {
                        'type': 'string',
                        'description': 'Python code to execute'
                    }
                },
                'required': ['code']
            }
        }
    
    def _register_browser_tools(self):
        """注册 Browser 工具（web_search, read_webpage, selenium_browse）"""
        # 导入 Browser 工具声明
        try:
            from ...gemini.browser import get_tool_declarations
            browser_tools = get_tool_declarations()
            
            for tool_decl in browser_tools:
                tool_name = tool_decl['name']
                self._registered_tools[tool_name] = {
                    'name': tool_name,
                    'description': tool_decl['description'],
                    'parameters': tool_decl['parameters']
                }
            
            logger.info(f"[ToolManager] Registered {len(browser_tools)} browser tools: {[t['name'] for t in browser_tools]}")
        except ImportError as e:
            logger.warning(f"[ToolManager] Failed to import browser tools: {e}")
        except Exception as e:
            logger.error(f"[ToolManager] Failed to register browser tools: {e}", exc_info=True)
    
    def get_tools(self) -> Optional[List[Any]]:
        """
        获取工具列表（GenAI SDK 格式）
        
        Returns:
            GenAI SDK Tool 对象列表，或 None
        """
        if not self._registered_tools:
            return None
        
        try:
            from google.genai import types as genai_types
            
            # 转换为 GenAI SDK Tool 格式
            tools = []
            for tool_name, tool_def in self._registered_tools.items():
                # 创建 FunctionDeclaration
                func_decl = genai_types.FunctionDeclaration(
                    name=tool_def['name'],
                    description=tool_def['description'],
                    parameters=tool_def['parameters']
                )
                
                # 创建 Tool（包含 FunctionDeclaration）
                tool = genai_types.Tool(
                    function_declarations=[func_decl]
                )
                tools.append(tool)
            
            logger.info(f"[ToolManager] Converted {len(tools)} tools to GenAI SDK format")
            return tools if tools else None
            
        except ImportError:
            # 如果导入失败，使用字典格式（向后兼容）
            logger.warning("[ToolManager] google.genai.types not available, using dict format")
            tools = []
            for tool_name, tool_def in self._registered_tools.items():
                tools.append({
                    'function_declarations': [{
                        'name': tool_def['name'],
                        'description': tool_def['description'],
                        'parameters': tool_def['parameters']
                    }]
                })
            return tools if tools else None
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            args: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            if tool_name == 'google_search':
                return await self._execute_google_search(args.get('query', ''))
            elif tool_name == 'file_search':
                return await self._execute_file_search(
                    args.get('query', ''),
                    args.get('store_names', [])
                )
            elif tool_name == 'code_execution':
                return await self._execute_code(args.get('code', ''))
            elif tool_name in ['web_search', 'read_webpage', 'selenium_browse']:
                # Browser 工具
                return await self._execute_browser_tool(tool_name, args)
            else:
                return {
                    'error': f'Unknown tool: {tool_name}'
                }
        except Exception as e:
            logger.error(f"[ToolManager] Tool execution failed: {e}", exc_info=True)
            return {
                'error': str(e)
            }
    
    async def _execute_google_search(self, query: str) -> Dict[str, Any]:
        """执行 Google Search"""
        # TODO: 实现 Google Search 工具调用
        # 可以使用现有的搜索服务或 API
        logger.info(f"[ToolManager] Google Search: {query}")
        return {
            'result': f'Search results for: {query}',
            'sources': []
        }
    
    async def _execute_file_search(self, query: str, store_names: List[str]) -> Dict[str, Any]:
        """执行 File Search"""
        # TODO: 实现 File Search 工具调用
        # 使用 File Search API
        logger.info(f"[ToolManager] File Search: {query} in {store_names}")
        return {
            'result': f'File search results for: {query}',
            'matches': []
        }
    
    async def _execute_code(self, code: str) -> Dict[str, Any]:
        """执行代码"""
        # TODO: 实现 Code Execution
        # 使用现有的 Code Executor
        logger.info(f"[ToolManager] Code Execution: {code[:50]}...")
        return {
            'result': 'Code execution result',
            'output': ''
        }
    
    async def _execute_browser_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 Browser 工具
        
        Args:
            tool_name: 工具名称（web_search, read_webpage, selenium_browse）
            args: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            # 导入 Browser 工具
            from ...gemini.browser import AVAILABLE_TOOLS
            
            if tool_name not in AVAILABLE_TOOLS:
                return {
                    'error': f'Browser tool {tool_name} not found'
                }
            
            tool_func = AVAILABLE_TOOLS[tool_name]
            logger.info(f"[ToolManager] Executing browser tool: {tool_name} with args: {args}")
            
            # 执行工具（可能是同步或异步）
            import asyncio
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**args)
            else:
                # 同步函数在异步上下文中执行
                result = await asyncio.to_thread(tool_func, **args)
            
            # 处理 selenium_browse 返回的结构化响应
            if tool_name == 'selenium_browse':
                if isinstance(result, dict):
                    if result.get('error'):
                        return {
                            'error': result['error']
                        }
                    else:
                        return {
                            'result': result.get('content', ''),
                            'screenshot': result.get('screenshot'),  # Base64 截图
                            'success': True
                        }
            
            # 其他工具返回字符串
            return {
                'result': result if isinstance(result, str) else str(result),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"[ToolManager] Browser tool execution failed: {e}", exc_info=True)
            return {
                'error': str(e),
                'success': False
            }
