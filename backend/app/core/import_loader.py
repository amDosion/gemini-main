"""
统一的模块导入工具

此模块提供统一的 fallback import 策略，避免在 main.py 中重复大量的 try-except 导入代码。

支持三种导入路径：
1. 相对导入：.services.xxx (推荐，当作为模块运行时)
2. 绝对导入：services.xxx (直接运行时)
3. 完整路径：backend.app.services.xxx (从项目根目录运行时)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Callable
import importlib

logger = logging.getLogger(__name__)


class ImportResult:
    """导入结果封装"""

    def __init__(
        self,
        success: bool,
        module: Any = None,
        attrs: Dict[str, Any] = None,
        error: Optional[Exception] = None
    ):
        self.success = success
        self.module = module
        self.attrs = attrs or {}
        self.error = error

    def get(self, attr_name: str, default: Any = None) -> Any:
        """获取导入的属性"""
        return self.attrs.get(attr_name, default)

    def __getitem__(self, attr_name: str) -> Any:
        """支持字典式访问"""
        return self.attrs[attr_name]


def safe_import(
    relative_path: str,
    attr_names: Optional[List[str]] = None,
    fallback_values: Optional[Dict[str, Any]] = None,
    warning_message: Optional[str] = None,
    info_message: Optional[str] = None
) -> ImportResult:
    """
    统一的 fallback import 函数

    Args:
        relative_path: 相对导入路径（不带前导点），如 'core.logger' 或 'services.gemini.common.browser'
        attr_names: 要导入的属性名列表，如 ['setup_logger', 'LOG_PREFIXES']
        fallback_values: 导入失败时的 fallback 值字典，如 {'SELENIUM_AVAILABLE': False}
        warning_message: 导入失败时的警告消息
        info_message: 导入失败时的提示消息（如安装说明）

    Returns:
        ImportResult: 包含导入结果的对象

    Example:
        >>> result = safe_import(
        ...     'services.gemini.common.browser',
        ...     attr_names=['read_webpage', 'selenium_browse', 'SELENIUM_AVAILABLE'],
        ...     fallback_values={
        ...         'SELENIUM_AVAILABLE': False,
        ...         'read_webpage': lambda *a, **k: RuntimeError("Not available"),
        ...         'selenium_browse': lambda *a, **k: RuntimeError("Not available")
        ...     },
        ...     warning_message="Could not import browser module"
        ... )
        >>> SELENIUM_AVAILABLE = result.get('SELENIUM_AVAILABLE')
        >>> read_webpage = result.get('read_webpage')
    """
    # 定义导入路径（优先使用 backend.app.xxx）
    import_paths = [
        f"backend.app.{relative_path}",  # 完整路径 (from backend.app.core.xxx) - 从项目根目录运行
        f"app.{relative_path}",  # 从 app 包导入 (from app.core.xxx) - 从 backend 目录运行
        f".{relative_path}",  # 相对导入 (from .core.xxx)
        relative_path,  # 绝对导入 (from core.xxx)
    ]

    last_error = None

    # 尝试导入路径
    for import_path in import_paths:
        try:
            # 动态导入模块
            if import_path.startswith('.'):
                # 相对导入需要指定 package
                module = importlib.import_module(import_path, package='app')
            else:
                # 绝对导入
                module = importlib.import_module(import_path)

            # 提取指定的属性
            attrs = {}
            if attr_names:
                for attr_name in attr_names:
                    if hasattr(module, attr_name):
                        attrs[attr_name] = getattr(module, attr_name)
                    else:
                        # 属性不存在，使用 fallback
                        if fallback_values and attr_name in fallback_values:
                            attrs[attr_name] = fallback_values[attr_name]
                        else:
                            # 没有 fallback，返回 None
                            attrs[attr_name] = None

            return ImportResult(success=True, module=module, attrs=attrs)

        except ImportError as e:
            last_error = e
            continue

    # 所有路径都失败了
    if warning_message:
        # 获取 LOG_PREFIXES（如果可用）
        try:
            from .logger import LOG_PREFIXES
            prefix = LOG_PREFIXES.get('warning', '⚠️')
        except:
            prefix = '⚠️'

        logger.warning(f"{prefix} {warning_message}: {last_error}")

    if info_message:
        logger.info(info_message)

    # 返回 fallback 值
    attrs = fallback_values.copy() if fallback_values else {}
    return ImportResult(success=False, attrs=attrs, error=last_error)


def safe_import_multiple(configs: List[Dict[str, Any]]) -> Dict[str, ImportResult]:
    """
    批量导入多个模块

    Args:
        configs: 导入配置列表，每个配置是一个字典，包含 safe_import 的参数

    Returns:
        Dict[str, ImportResult]: 模块名 -> 导入结果的字典

    Example:
        >>> configs = [
        ...     {
        ...         'name': 'logger',
        ...         'relative_path': 'core.logger',
        ...         'attr_names': ['setup_logger', 'LOG_PREFIXES']
        ...     },
        ...     {
        ...         'name': 'browser',
        ...         'relative_path': 'services.gemini.common.browser',
        ...         'attr_names': ['read_webpage', 'SELENIUM_AVAILABLE'],
        ...         'fallback_values': {'SELENIUM_AVAILABLE': False}
        ...     }
        ... ]
        >>> results = safe_import_multiple(configs)
        >>> logger = results['logger'].get('setup_logger')("main")
    """
    results = {}

    for config in configs:
        name = config.pop('name')
        result = safe_import(**config)
        results[name] = result

    return results


def create_fallback_function(error_message: str) -> Callable:
    """
    创建一个 fallback 函数，调用时抛出 RuntimeError

    Args:
        error_message: 错误消息

    Returns:
        Callable: fallback 函数

    Example:
        >>> read_webpage = create_fallback_function("Browser module not available")
        >>> read_webpage("http://example.com")  # 抛出 RuntimeError
    """
    def fallback(*args, **kwargs):
        raise RuntimeError(error_message)

    return fallback


def create_fallback_class(error_message: str) -> type:
    """
    创建一个 fallback 类，访问任何属性时抛出 RuntimeError

    Args:
        error_message: 错误消息

    Returns:
        type: fallback 类

    Example:
        >>> DummyRAGService = create_fallback_class("Embedding service not available")
        >>> service = DummyRAGService()
        >>> service.some_method()  # 抛出 RuntimeError
    """
    class FallbackClass:
        def __getattr__(self, name):
            raise RuntimeError(error_message)

    return FallbackClass
