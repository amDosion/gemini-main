"""
通义千问错误处理 Mixin - DashScope SDK 错误码映射

从 chat.py 拆分而来（行为完全一致），保存 DashScope 错误码到统一异常体系的
映射逻辑。被 QwenNativeProvider 通过 mixin 继承复用。

依赖说明：这些方法访问 self.connection_mode / self.request_id（由
QwenNativeProvider.__init__ 设置），并复用统一错误系统中的异常类型。
"""

from typing import Dict, Optional

from ..common.errors import (
    OperationError,
    APIKeyError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError,
    ErrorContext,
)


class _QwenErrorHandlingMixin:
    """DashScope 错误处理 Mixin（供 QwenNativeProvider 继承）"""

    # ==================== 辅助方法 ====================

    def _get_error_map(self) -> Dict[str, type]:
        """
        获取 DashScope 特定的错误码映射

        Returns:
            错误码到异常类的映射
        """
        return {
            "InvalidApiKey": APIKeyError,
            "InvalidAPIKey": APIKeyError,
            "Throttling.RateQuota": RateLimitError,
            "Throttling.AllocationQuota": RateLimitError,
            "InvalidModel": ModelNotFoundError,
            "UnsupportedModel": ModelNotFoundError,
            "InvalidParameter": InvalidRequestError,
            "InvalidInput": InvalidRequestError,
        }

    def _handle_error(self, error_code: str, error_message: str, error_map: Dict[str, type],
                      operation: str = "unknown", model: Optional[str] = None):
        """
        处理 DashScope API 错误，使用统一错误处理系统

        Args:
            error_code: 错误码
            error_message: 错误信息
            error_map: 错误码到异常类的映射
            operation: 操作类型 (chat, stream_chat, multimodal_chat 等)
            model: 模型名称
        """
        # 创建错误上下文
        context = ErrorContext(
            provider_id="qwen",
            client_type="primary" if self.connection_mode == "official" else "secondary",
            operation=operation,
            request_id=self.request_id,
            model=model,
            additional_context={
                "error_code": error_code,
                "connection_mode": self.connection_mode
            }
        )

        # 查找对应的异常类
        exception_class = error_map.get(error_code)

        if exception_class == APIKeyError:
            raise APIKeyError(context=context)
        elif exception_class == RateLimitError:
            raise RateLimitError(context=context)
        elif exception_class == ModelNotFoundError:
            raise ModelNotFoundError(context=context)
        elif exception_class == InvalidRequestError:
            raise InvalidRequestError(context=context)
        else:
            # 未知错误，使用 OperationError
            raise OperationError(
                message=f"[{error_code}] {error_message}",
                context=context,
                recoverable=True
            )
