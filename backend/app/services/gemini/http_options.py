"""HTTP options for the unified Gemini client pool.

历史背景：
    这三个类原本住在 `services/gemini/agent/types.py`，与一堆 SDK 兼容类型
    （Part / Content / GenerateContentConfig 等）混在一起。但 HttpOptions 是
    GeminiClientPool / google_service / coordinators / interactions_manager 共用
    的客户端配置层类型，不应当绑死在 agent/ 子包里。

    本文件把它们抽离出来作为 services.gemini 的 1st-class 类型；
    为兼容性，agent/types.py 仍 re-export 这三个名字（在迁移完成前不删）。

字段约定与 google.genai.types.HttpOptions / HttpRetryOptions 对齐，便于在
    `services/gemini/client_pool.py:_to_genai_http_options` 内做无损映射。
"""

from typing import Dict, Optional
from typing_extensions import TypedDict

import pydantic


class _HttpOptionsBase(pydantic.BaseModel):
    """pydantic 基类配置，与 agent.common.BaseModel 一致。"""

    model_config = pydantic.ConfigDict(
        extra="allow",
        populate_by_name=True,
    )


class HttpRetryOptions(_HttpOptionsBase):
    """HTTP retry configuration.

    与原 agent/types.py 版本相比补全了 ``exp_base`` 与 ``jitter`` 字段——
    旧版本仅声明三个字段，运行时依赖 ``extra='allow'`` 动态接收，
    类型系统看不见 client_pool.py 实际在传的这两个参数。
    """

    attempts: Optional[int] = None
    initial_delay: Optional[float] = None
    max_delay: Optional[float] = None
    exp_base: Optional[float] = None
    jitter: Optional[bool] = None


class HttpOptions(_HttpOptionsBase):
    """HTTP client configuration."""

    api_version: Optional[str] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None
    retry_options: Optional[HttpRetryOptions] = None
    use_default_timeout: bool = True


class HttpOptionsDict(TypedDict, total=False):
    """Dictionary version of HttpOptions for kwargs-style construction."""

    api_version: str
    base_url: str
    headers: Dict[str, str]
    timeout: Optional[int]
    retry_options: HttpRetryOptions
    use_default_timeout: bool


__all__ = ["HttpOptions", "HttpOptionsDict", "HttpRetryOptions"]
