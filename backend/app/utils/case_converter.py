"""
camelCase <-> snake_case 转换工具

用于中间件自动转换请求/响应的命名格式：
- 请求：前端 camelCase -> 后端 snake_case
- 响应：后端 snake_case -> 前端 camelCase

注意：某些字段的值是业务数据，不应该递归转换其内部的 key。
例如：toolArgs、arguments、extra、metadata、multiAgentConfig 等。
"""
import re
from typing import Any, Set, Optional


# 不应该递归转换值的字段名（camelCase 和 snake_case 都列出）
# 这些字段的值是业务数据/外部结构，应该保持原样
SKIP_VALUE_CONVERSION_FIELDS: Set[str] = {
    # ========== 工具调用相关 ==========
    'toolArgs', 'tool_args',              # 工具调用参数（业务数据）
    'toolResult', 'tool_result',          # 工具调用结果（业务数据）
    'toolCalls', 'tool_calls',            # 工具调用列表（业务数据）
    'toolResults', 'tool_results',        # 工具结果列表（业务数据）
    'arguments',                          # 函数参数（通用）
    'args',                               # 参数（通用）
    'parameters',                         # 参数配置

    # ========== 元数据相关 ==========
    'extra',                              # 额外数据
    'metadata',                           # 元数据（业务数据）
    'rawData', 'raw_data',                # 原始数据
    'customData', 'custom_data',          # 自定义数据（业务数据）

    # ========== 配置相关（用户自定义结构）==========
    'multiAgentConfig', 'multi_agent_config',           # 多智能体配置
    'deepResearchConfig', 'deep_research_config',       # 深度研究配置
    'liveAPIConfig', 'live_api_config', 'live_a_p_i_config',  # Live API 配置
    'outPainting', 'out_painting',                      # 扩图配置
    'loraConfig', 'lora_config',                        # LoRA 配置
    # 注意：移除了通用的 'config' 字段，以允许存储配置等后端API的config被正确转换

    # ========== JSON Schema 相关 ==========
    'schema',                             # JSON Schema
    'jsonSchema', 'json_schema',          # JSON Schema
    'inputSchema', 'input_schema',        # 输入 Schema
    'outputSchema', 'output_schema',      # 输出 Schema

    # ========== 外部服务响应 ==========
    'payload',                            # 外部 API payload
    'body',                               # 请求/响应 body
    'data',                               # 通用数据字段（注意：比较通用，可能需要调整）
    'result',                             # 结果数据
    'response',                           # 响应数据

    # ========== 其他业务数据 ==========
    'thinking',                           # 思考内容（业务数据）
    'context',                            # 上下文（可能包含任意结构）
    'state',                              # 状态数据
}


def camel_to_snake(name: str) -> str:
    """
    将 camelCase 转换为 snake_case

    Examples:
        camelCase -> camel_case
        XMLParser -> xml_parser
        getHTTPResponse -> get_http_response
    """
    # 处理连续大写字母（如 XMLParser -> xml_parser）
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str) -> str:
    """
    将 snake_case 转换为 camelCase

    Examples:
        snake_case -> snakeCase
        get_http_response -> getHttpResponse
    """
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_snake_case(
    data: Any, 
    skip_fields: Optional[Set[str]] = None,
    _current_key: Optional[str] = None
) -> Any:
    """
    递归转换所有键为 snake_case

    支持：dict, list, 嵌套结构
    
    对于 SKIP_VALUE_CONVERSION_FIELDS 中的字段，只转换该字段的 key，
    不递归转换其 value 内部的 key。

    Args:
        data: 要转换的数据（dict, list, 或其他）
        skip_fields: 额外需要跳过的字段名集合（可选）
        _current_key: 内部使用，当前正在处理的 key 名

    Returns:
        转换后的数据，键名为 snake_case
    """
    # 合并默认跳过字段和自定义跳过字段
    all_skip_fields = SKIP_VALUE_CONVERSION_FIELDS
    if skip_fields:
        all_skip_fields = all_skip_fields | skip_fields
    
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            new_key = camel_to_snake(k)
            # 检查是否需要跳过该字段值的递归转换
            if k in all_skip_fields or new_key in all_skip_fields:
                # 只转换 key，value 保持原样
                result[new_key] = v
            else:
                # 递归转换
                result[new_key] = to_snake_case(v, skip_fields, k)
        return result
    elif isinstance(data, list):
        return [to_snake_case(item, skip_fields, _current_key) for item in data]
    else:
        return data


def to_camel_case(
    data: Any,
    skip_fields: Optional[Set[str]] = None,
    _current_key: Optional[str] = None
) -> Any:
    """
    递归转换所有键为 camelCase

    支持：dict, list, 嵌套结构
    
    对于 SKIP_VALUE_CONVERSION_FIELDS 中的字段，只转换该字段的 key，
    不递归转换其 value 内部的 key。

    Args:
        data: 要转换的数据（dict, list, 或其他）
        skip_fields: 额外需要跳过的字段名集合（可选）
        _current_key: 内部使用，当前正在处理的 key 名

    Returns:
        转换后的数据，键名为 camelCase
    """
    # 合并默认跳过字段和自定义跳过字段
    all_skip_fields = SKIP_VALUE_CONVERSION_FIELDS
    if skip_fields:
        all_skip_fields = all_skip_fields | skip_fields
    
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            new_key = snake_to_camel(k)
            # 检查是否需要跳过该字段值的递归转换
            if k in all_skip_fields or new_key in all_skip_fields:
                # 只转换 key，value 保持原样
                result[new_key] = v
            else:
                # 递归转换
                result[new_key] = to_camel_case(v, skip_fields, k)
        return result
    elif isinstance(data, list):
        return [to_camel_case(item, skip_fields, _current_key) for item in data]
    else:
        return data
