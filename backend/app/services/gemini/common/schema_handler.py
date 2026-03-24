"""
Gemini JSON Schema Response Handler

处理结构化响应输出的专门模块。
支持 JSON Schema、Pydantic 模型、枚举类型等结构化输出格式。
"""

import json
from typing import Optional, Dict, Any, Type, Union, get_type_hints
from enum import Enum
from pydantic import BaseModel

class SchemaHandler:
    """Gemini JSON Schema 响应处理器"""

    def __init__(self, *, api_key=None, use_vertex=False, project=None, location=None, http_options=None):
        """
        初始化 Schema 处理器

        Args:
            client_factory: A callable that returns a configured Gemini client
        """
        self._api_key = api_key
        self._use_vertex = use_vertex
        self._project = project
        self._location = location
        self._http_options = http_options
    
    def create_json_schema_config(
        self,
        schema: Dict[str, Any],
        mime_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """
        创建 JSON Schema 配置
        
        Args:
            schema: JSON Schema 定义
            mime_type: 响应 MIME 类型
            
        Returns:
            生成内容配置字典
        """
        return {
            'response_mime_type': mime_type,
            'response_json_schema': schema
        }
    
    def create_pydantic_schema_config(
        self,
        model_class: Type[BaseModel],
        mime_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """
        从 Pydantic 模型创建 Schema 配置
        
        Args:
            model_class: Pydantic 模型类
            mime_type: 响应 MIME 类型
            
        Returns:
            生成内容配置字典
        """
        return {
            'response_mime_type': mime_type,
            'response_schema': model_class
        }
    
    def create_enum_schema_config(
        self,
        enum_class: Type[Enum],
        mime_type: str = 'text/x.enum'
    ) -> Dict[str, Any]:
        """
        从枚举类创建 Schema 配置
        
        Args:
            enum_class: 枚举类
            mime_type: 响应 MIME 类型（text/x.enum 或 application/json）
            
        Returns:
            生成内容配置字典
        """
        return {
            'response_mime_type': mime_type,
            'response_schema': enum_class
        }
    
    def parse_structured_response(
        self,
        response: Any,
        target_type: Optional[Type] = None
    ) -> Union[Dict[str, Any], BaseModel, Any]:
        """
        解析结构化响应
        
        Args:
            response: 模型响应
            target_type: 目标类型（可选）
            
        Returns:
            解析后的结构化数据
        """
        # 如果响应有 parsed 属性，直接返回
        if hasattr(response, 'parsed') and response.parsed is not None:
            return response.parsed
        
        # 尝试从 text 属性解析 JSON
        if hasattr(response, 'text'):
            try:
                json_data = json.loads(response.text)
                
                # 如果指定了目标类型，尝试转换
                if target_type and issubclass(target_type, BaseModel):
                    return target_type(**json_data)
                
                return json_data
            except json.JSONDecodeError:
                # 如果不是 JSON，返回原始文本
                return response.text
        
        return response
    
    def create_object_schema(
        self,
        properties: Dict[str, Dict[str, Any]],
        required: Optional[list] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建对象 Schema
        
        Args:
            properties: 属性定义
            required: 必需属性列表
            title: Schema 标题
            description: Schema 描述
            
        Returns:
            JSON Schema 字典
        """
        schema = {
            'type': 'object',
            'properties': properties
        }
        
        if required:
            schema['required'] = required
        
        if title:
            schema['title'] = title
        
        if description:
            schema['description'] = description
        
        return schema
    
    def create_array_schema(
        self,
        items_schema: Dict[str, Any],
        min_items: Optional[int] = None,
        max_items: Optional[int] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建数组 Schema
        
        Args:
            items_schema: 数组项 Schema
            min_items: 最小项数
            max_items: 最大项数
            title: Schema 标题
            description: Schema 描述
            
        Returns:
            JSON Schema 字典
        """
        schema = {
            'type': 'array',
            'items': items_schema
        }
        
        if min_items is not None:
            schema['minItems'] = min_items
        
        if max_items is not None:
            schema['maxItems'] = max_items
        
        if title:
            schema['title'] = title
        
        if description:
            schema['description'] = description
        
        return schema
    
    def create_string_schema(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        enum_values: Optional[list] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建字符串 Schema
        
        Args:
            min_length: 最小长度
            max_length: 最大长度
            pattern: 正则表达式模式
            enum_values: 枚举值列表
            title: Schema 标题
            description: Schema 描述
            
        Returns:
            JSON Schema 字典
        """
        schema = {
            'type': 'string'
        }
        
        if min_length is not None:
            schema['minLength'] = min_length
        
        if max_length is not None:
            schema['maxLength'] = max_length
        
        if pattern:
            schema['pattern'] = pattern
        
        if enum_values:
            schema['enum'] = enum_values
        
        if title:
            schema['title'] = title
        
        if description:
            schema['description'] = description
        
        return schema
    
    def create_number_schema(
        self,
        number_type: str = 'number',
        minimum: Optional[Union[int, float]] = None,
        maximum: Optional[Union[int, float]] = None,
        multiple_of: Optional[Union[int, float]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建数字 Schema
        
        Args:
            number_type: 数字类型（'number' 或 'integer'）
            minimum: 最小值
            maximum: 最大值
            multiple_of: 倍数
            title: Schema 标题
            description: Schema 描述
            
        Returns:
            JSON Schema 字典
        """
        schema = {
            'type': number_type
        }
        
        if minimum is not None:
            schema['minimum'] = minimum
        
        if maximum is not None:
            schema['maximum'] = maximum
        
        if multiple_of is not None:
            schema['multipleOf'] = multiple_of
        
        if title:
            schema['title'] = title
        
        if description:
            schema['description'] = description
        
        return schema
    
    def create_boolean_schema(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建布尔 Schema
        
        Args:
            title: Schema 标题
            description: Schema 描述
            
        Returns:
            JSON Schema 字典
        """
        schema = {
            'type': 'boolean'
        }
        
        if title:
            schema['title'] = title
        
        if description:
            schema['description'] = description
        
        return schema
    
    def validate_response_against_schema(
        self,
        response_data: Any,
        schema: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        验证响应数据是否符合 Schema
        
        Args:
            response_data: 响应数据
            schema: JSON Schema
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            import jsonschema
            jsonschema.validate(response_data, schema)
            return True, None
        except ImportError:
            # 如果没有安装 jsonschema，进行简单验证
            return self._simple_schema_validation(response_data, schema)
        except Exception as e:
            return False, str(e)
    
    def _simple_schema_validation(
        self,
        data: Any,
        schema: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        简单的 Schema 验证（不依赖 jsonschema 库）
        
        Args:
            data: 数据
            schema: Schema
            
        Returns:
            (是否有效, 错误信息)
        """
        schema_type = schema.get('type')
        
        if schema_type == 'object':
            if not isinstance(data, dict):
                return False, f"期望对象类型，得到 {type(data).__name__}"
            
            # 检查必需属性
            required = schema.get('required', [])
            for prop in required:
                if prop not in data:
                    return False, f"缺少必需属性: {prop}"
            
            return True, None
        
        elif schema_type == 'array':
            if not isinstance(data, list):
                return False, f"期望数组类型，得到 {type(data).__name__}"
            
            return True, None
        
        elif schema_type == 'string':
            if not isinstance(data, str):
                return False, f"期望字符串类型，得到 {type(data).__name__}"
            
            return True, None
        
        elif schema_type == 'number':
            if not isinstance(data, (int, float)):
                return False, f"期望数字类型，得到 {type(data).__name__}"
            
            return True, None
        
        elif schema_type == 'integer':
            if not isinstance(data, int):
                return False, f"期望整数类型，得到 {type(data).__name__}"
            
            return True, None
        
        elif schema_type == 'boolean':
            if not isinstance(data, bool):
                return False, f"期望布尔类型，得到 {type(data).__name__}"
            
            return True, None
        
        return True, None


# 预定义的常用 Schema 模板
class CommonSchemas:
    """常用 Schema 模板"""
    
    @staticmethod
    def user_profile_schema() -> Dict[str, Any]:
        """用户资料 Schema"""
        return {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': '用户姓名'},
                'age': {'type': 'integer', 'minimum': 0, 'maximum': 150},
                'email': {'type': 'string', 'pattern': r'^[^@]+@[^@]+\.[^@]+$'},
                'interests': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '兴趣爱好列表'
                }
            },
            'required': ['name', 'email']
        }
    
    @staticmethod
    def task_schema() -> Dict[str, Any]:
        """任务 Schema"""
        return {
            'type': 'object',
            'properties': {
                'title': {'type': 'string', 'description': '任务标题'},
                'description': {'type': 'string', 'description': '任务描述'},
                'priority': {
                    'type': 'string',
                    'enum': ['low', 'medium', 'high'],
                    'description': '优先级'
                },
                'due_date': {'type': 'string', 'format': 'date'},
                'completed': {'type': 'boolean', 'default': False}
            },
            'required': ['title', 'priority']
        }
    
    @staticmethod
    def analysis_result_schema() -> Dict[str, Any]:
        """分析结果 Schema"""
        return {
            'type': 'object',
            'properties': {
                'summary': {'type': 'string', 'description': '分析摘要'},
                'key_points': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '关键要点'
                },
                'confidence_score': {
                    'type': 'number',
                    'minimum': 0,
                    'maximum': 1,
                    'description': '置信度分数'
                },
                'recommendations': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '建议列表'
                }
            },
            'required': ['summary', 'confidence_score']
        }