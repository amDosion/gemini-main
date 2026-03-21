"""
MCP Schema 工具
用于转换和过滤 JSON Schema，使其兼容不同的 AI 模型
参考 Google Gemini SDK 的 _mcp_utils.py 实现
"""

from typing import Dict, Any, List, Set
import logging

logger = logging.getLogger(__name__)


# Union 关键字兼容映射（输入兼容 snake_case，输出统一 camelCase）
COMPOSITE_FIELD_ALIASES: Dict[str, str] = {
    "any_of": "anyOf",
    "one_of": "oneOf",
    "all_of": "allOf",
}


# Gemini/OpenAI 支持的 Schema 字段（统一使用 canonical key）
SUPPORTED_SCHEMA_FIELDS: Set[str] = {
    "type",
    "description",
    "properties",
    "required",
    "items",
    "anyOf",
    "oneOf",
    "allOf",
    "enum",
    "format",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "pattern",
    "default",
    "additionalProperties",
    "$ref",
    "$defs",
    "definitions",
    "title",
}

# 需要递归处理的单个 Schema 字段
SINGLE_SCHEMA_FIELDS: Set[str] = {
    "items",
    "additionalProperties",
}

# 需要递归处理的 Schema 列表字段
LIST_SCHEMA_FIELDS: Set[str] = {
    "anyOf",
    "oneOf",
    "allOf",
}

# 需要递归处理的 Schema 字典字段
DICT_SCHEMA_FIELDS: Set[str] = {
    "properties",
    "$defs",
    "definitions",
}


COMPOSITE_SCHEMA_FIELDS: Set[str] = {
    "anyOf",
    "oneOf",
    "allOf",
}


def _canonicalize_schema_field(field_name: str) -> str:
    """Normalize schema field aliases to canonical camelCase key."""
    return COMPOSITE_FIELD_ALIASES.get(field_name, field_name)


def filter_supported_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    过滤 Schema，移除不支持的字段

    参考 Google Gemini SDK 的 _filter_to_supported_schema 实现

    Args:
        schema: 原始 MCP JSON Schema

    Returns:
        过滤后的 Schema（仅包含支持的字段）

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {"name": {"type": "string"}},
        ...     "unknown_field": "should be removed"
        ... }
        >>> filtered = filter_supported_schema(schema)
        >>> "unknown_field" in filtered
        False
    """
    if not isinstance(schema, dict):
        return schema

    filtered: Dict[str, Any] = {}

    for field_name, field_value in schema.items():
        canonical_field_name = _canonicalize_schema_field(field_name)

        # 跳过不支持的字段
        if canonical_field_name not in SUPPORTED_SCHEMA_FIELDS:
            logger.debug(f"Filtering out unsupported field: {field_name}")
            continue

        # 递归处理单个 Schema 字段（如 items）
        if canonical_field_name in SINGLE_SCHEMA_FIELDS:
            if isinstance(field_value, dict):
                filtered[canonical_field_name] = filter_supported_schema(field_value)
            else:
                filtered[canonical_field_name] = field_value

        # 递归处理 Schema 列表字段（如 any_of）
        elif canonical_field_name in LIST_SCHEMA_FIELDS:
            if isinstance(field_value, list):
                filtered[canonical_field_name] = [
                    filter_supported_schema(item) if isinstance(item, dict) else item
                    for item in field_value
                ]
            else:
                filtered[canonical_field_name] = field_value

        # 递归处理 Schema 字典字段（如 properties）
        elif canonical_field_name in DICT_SCHEMA_FIELDS:
            if isinstance(field_value, dict):
                filtered[canonical_field_name] = {
                    key: filter_supported_schema(value) if isinstance(value, dict) else value
                    for key, value in field_value.items()
                }
            else:
                filtered[canonical_field_name] = field_value

        # 保留其他支持的字段
        else:
            filtered[canonical_field_name] = field_value

    return filtered


def mcp_schema_to_gemini_schema(mcp_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 MCP JSON Schema 转换为 Gemini Schema 格式

    主要变更：
    - 过滤不支持的字段
    - 转换字段名（snake_case → camelCase）
    - 规范化类型值

    Args:
        mcp_schema: MCP 工具的 inputSchema

    Returns:
        Gemini 兼容的 Schema

    Example:
        >>> mcp_schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "location": {"type": "string", "description": "City name"}
        ...     },
        ...     "required": ["location"]
        ... }
        >>> gemini_schema = mcp_schema_to_gemini_schema(mcp_schema)
        >>> gemini_schema["type"]
        'object'
    """
    # 先过滤不支持的字段
    filtered = filter_supported_schema(mcp_schema)

    # 转换类型值（可选，Gemini 一般支持小写）
    if "type" in filtered:
        filtered["type"] = filtered["type"].lower()

    return filtered


def mcp_schema_to_openai_schema(mcp_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 MCP JSON Schema 转换为 OpenAI Function Schema 格式

    OpenAI 的 Schema 与标准 JSON Schema 更接近，
    但仍需要过滤一些高级特性

    Args:
        mcp_schema: MCP 工具的 inputSchema

    Returns:
        OpenAI 兼容的 Schema
    """
    # OpenAI 支持更多字段，这里做基础过滤
    filtered = filter_supported_schema(mcp_schema)

    return filtered


def normalize_schema_type(schema_type: str) -> str:
    """
    规范化 Schema 类型值

    Args:
        schema_type: 原始类型（如 "STRING", "OBJECT"）

    Returns:
        规范化的类型（如 "string", "object"）
    """
    type_map = {
        "STRING": "string",
        "NUMBER": "number",
        "INTEGER": "integer",
        "BOOLEAN": "boolean",
        "OBJECT": "object",
        "ARRAY": "array",
        "NULL": "null"
    }

    return type_map.get(schema_type.upper(), schema_type.lower())


def validate_schema(schema: Dict[str, Any]) -> List[str]:
    """
    验证 Schema 的有效性

    Args:
        schema: 要验证的 Schema

    Returns:
        错误列表（空列表表示无错误）

    Example:
        >>> schema = {"type": "object"}
        >>> errors = validate_schema(schema)
        >>> len(errors)
        0
    """
    errors: List[str] = []

    if not isinstance(schema, dict):
        return ["Schema must be an object"]

    # 先做字段规范化，保证 any_of/one_of/all_of 兼容输入后统一校验
    schema = filter_supported_schema(schema)

    # 顶层可由 type / 组合关键字 / $ref 任一声明
    if (
        "type" not in schema
        and "$ref" not in schema
        and not any(field in schema for field in COMPOSITE_SCHEMA_FIELDS)
    ):
        errors.append("Schema must have 'type' field")

    # 如果是 object 类型，应该有 properties
    if schema.get("type") == "object":
        if "properties" not in schema:
            logger.warning("Object type schema without 'properties' field")

    # 如果是 array 类型，应该有 items
    if schema.get("type") == "array":
        if "items" not in schema:
            errors.append("Array type schema must have 'items' field")

    # 组合字段必须是列表
    for composite_field in COMPOSITE_SCHEMA_FIELDS:
        if composite_field in schema and not isinstance(schema[composite_field], list):
            errors.append(f"'{composite_field}' field must be a list")

    # $ref 必须是字符串
    if "$ref" in schema and not isinstance(schema["$ref"], str):
        errors.append("'$ref' field must be a string")

    # 验证 required 字段
    if "required" in schema:
        if not isinstance(schema["required"], list):
            errors.append("'required' field must be a list")
        elif "properties" in schema:
            properties = schema["properties"]
            for req_field in schema["required"]:
                if req_field not in properties:
                    errors.append(f"Required field '{req_field}' not in properties")

    return errors
