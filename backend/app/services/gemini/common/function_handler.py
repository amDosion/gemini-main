"""
Gemini Function Calling Handler

处理函数调用和工具集成的专门模块。
支持自动函数调用、手动函数声明、工具配置等功能。
"""

import inspect
import json
import asyncio
from typing import Optional, List, Dict, Any, Callable, Union
from enum import Enum

from .sdk_initializer import SDKInitializer
from app.utils.safe_expression_eval import safe_eval_expression


class FunctionCallingMode(Enum):
    """函数调用模式"""
    AUTO = "AUTO"
    ANY = "ANY" 
    NONE = "NONE"


class FunctionHandler:
    """Gemini Function Calling 处理器"""
    
    def __init__(self, sdk_initializer: SDKInitializer):
        """
        初始化函数处理器
        
        Args:
            sdk_initializer: SDK 初始化器实例
        """
        self.sdk_initializer = sdk_initializer
        self.registered_functions: Dict[str, Callable] = {}
    
    def register_function(self, func: Callable, name: Optional[str] = None) -> str:
        """
        注册 Python 函数用于自动调用
        
        Args:
            func: Python 函数
            name: 函数名称（可选，默认使用函数名）
            
        Returns:
            注册的函数名称
        """
        function_name = name or func.__name__
        self.registered_functions[function_name] = func
        return function_name
    
    def unregister_function(self, name: str) -> bool:
        """
        取消注册函数
        
        Args:
            name: 函数名称
            
        Returns:
            是否成功取消注册
        """
        if name in self.registered_functions:
            del self.registered_functions[name]
            return True
        return False
    
    def create_function_declaration(
        self, 
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从 Python 函数创建函数声明
        
        Args:
            func: Python 函数
            name: 函数名称（可选）
            description: 函数描述（可选，从 docstring 获取）
            
        Returns:
            函数声明字典
        """
        function_name = name or func.__name__
        function_description = description or (func.__doc__ or f"调用 {function_name} 函数")
        
        # 获取函数签名
        sig = inspect.signature(func)
        parameters = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            param_info = {
                'type': 'string'  # 默认类型
            }
            
            # 从类型注解推断参数类型
            if param.annotation != inspect.Parameter.empty:
                param_type = self._get_json_type(param.annotation)
                param_info['type'] = param_type
            
            # 从 docstring 获取参数描述
            if func.__doc__:
                param_desc = self._extract_param_description(func.__doc__, param_name)
                if param_desc:
                    param_info['description'] = param_desc
            
            parameters[param_name] = param_info
            
            # 检查是否为必需参数
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            'name': function_name,
            'description': function_description,
            'parameters_json_schema': {
                'type': 'object',
                'properties': parameters,
                'required': required
            }
        }
    
    def create_manual_function_declaration(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        手动创建函数声明
        
        Args:
            name: 函数名称
            description: 函数描述
            parameters: 参数定义
            required: 必需参数列表
            
        Returns:
            函数声明字典
        """
        return {
            'name': name,
            'description': description,
            'parameters_json_schema': {
                'type': 'object',
                'properties': parameters,
                'required': required or []
            }
        }
    
    def create_tool_config(
        self,
        functions: List[Union[Callable, Dict[str, Any]]],
        mode: FunctionCallingMode = FunctionCallingMode.AUTO,
        allowed_function_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建工具配置
        
        Args:
            functions: 函数列表（Python 函数或函数声明字典）
            mode: 函数调用模式
            allowed_function_names: 允许调用的函数名称列表
            
        Returns:
            工具配置字典
        """
        # 处理函数声明
        function_declarations = []
        for func in functions:
            if callable(func):
                # Python 函数，自动创建声明
                declaration = self.create_function_declaration(func)
                function_declarations.append(declaration)
                # 自动注册函数
                self.register_function(func)
            elif isinstance(func, dict):
                # 手动函数声明
                function_declarations.append(func)
            else:
                raise ValueError(f"不支持的函数类型: {type(func)}")
        
        tool_config = {
            'tools': [{
                'function_declarations': function_declarations
            }]
        }
        
        # 添加函数调用配置
        if mode != FunctionCallingMode.AUTO or allowed_function_names:
            function_calling_config = {
                'mode': mode.value
            }
            
            if allowed_function_names:
                function_calling_config['allowed_function_names'] = allowed_function_names
            
            tool_config['tool_config'] = {
                'function_calling_config': function_calling_config
            }
        
        return tool_config
    
    async def execute_function_call(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行函数调用
        
        Args:
            function_call: 函数调用信息
            
        Returns:
            函数执行结果
        """
        function_name = function_call.get('name')
        function_args = function_call.get('args', {})
        
        if function_name not in self.registered_functions:
            return {
                'error': f"函数 '{function_name}' 未注册"
            }
        
        try:
            func = self.registered_functions[function_name]
            
            # 检查函数是否为异步函数
            if asyncio.iscoroutinefunction(func):
                result = await func(**function_args)
            else:
                result = func(**function_args)
            
            return {
                'result': result
            }
            
        except Exception as e:
            return {
                'error': f"函数执行失败: {str(e)}"
            }
    
    def create_function_response(
        self,
        function_call_id: str,
        function_name: str,
        result: Any,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建函数响应
        
        Args:
            function_call_id: 函数调用 ID
            function_name: 函数名称
            result: 执行结果
            error: 错误信息（可选）
            
        Returns:
            函数响应字典
        """
        response_data = {
            'result': result
        } if error is None else {
            'error': error
        }
        
        return {
            'name': function_name,
            'response': response_data,
            'id': function_call_id
        }
    
    def _get_json_type(self, python_type) -> str:
        """
        将 Python 类型转换为 JSON Schema 类型
        
        Args:
            python_type: Python 类型
            
        Returns:
            JSON Schema 类型字符串
        """
        type_mapping = {
            str: 'string',
            int: 'integer',
            float: 'number',
            bool: 'boolean',
            list: 'array',
            dict: 'object'
        }
        
        # 处理泛型类型
        if hasattr(python_type, '__origin__'):
            origin = python_type.__origin__
            if origin in type_mapping:
                return type_mapping[origin]
        
        # 处理基本类型
        if python_type in type_mapping:
            return type_mapping[python_type]
        
        # 默认返回 string
        return 'string'
    
    def _extract_param_description(self, docstring: str, param_name: str) -> Optional[str]:
        """
        从 docstring 中提取参数描述
        
        Args:
            docstring: 函数文档字符串
            param_name: 参数名称
            
        Returns:
            参数描述或 None
        """
        lines = docstring.split('\n')
        in_args_section = False
        
        for line in lines:
            line = line.strip()
            
            # 检查是否进入 Args 部分
            if line.lower().startswith('args:'):
                in_args_section = True
                continue
            
            # 检查是否离开 Args 部分
            if in_args_section and line and not line.startswith(' ') and ':' not in line:
                break
            
            # 在 Args 部分中查找参数
            if in_args_section and line.startswith(f'{param_name}:'):
                description = line[len(f'{param_name}:'):].strip()
                return description
        
        return None
    
    def get_registered_functions(self) -> List[str]:
        """
        获取已注册的函数列表
        
        Returns:
            函数名称列表
        """
        return list(self.registered_functions.keys())
    
    def clear_registered_functions(self):
        """清空所有已注册的函数"""
        self.registered_functions.clear()


# 预定义的常用工具函数示例
def get_current_time() -> str:
    """
    获取当前时间
    
    Returns:
        当前时间字符串
    """
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate_math_expression(expression: str) -> Union[float, str]:
    """
    计算数学表达式
    
    Args:
        expression: 数学表达式字符串
        
    Returns:
        计算结果或错误信息
    """
    try:
        result = safe_eval_expression(
            expression,
            variables={
                "pi": 3.141592653589793,
                "e": 2.718281828459045,
            },
            functions={
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
            },
        )
        return float(result)
    except Exception as e:
        return f"计算错误: {str(e)}"


def search_web(query: str, num_results: int = 5) -> str:
    """
    搜索网络信息（示例函数）
    
    Args:
        query: 搜索查询
        num_results: 结果数量
        
    Returns:
        搜索结果摘要
    """
    # 这里应该实现真实的网络搜索逻辑
    return f"搜索 '{query}' 的前 {num_results} 个结果（示例响应）"
