"""Vertex AI credentials helper.

历史背景：
    ``get_vertex_ai_credentials_from_db()`` 原住在
    ``services/gemini/agent/client.py``，但它和 agent 兼容层无关，
    本质是个 ``VertexAIConfig`` 表查询 + service-account JSON 解密的工具函数。
    本文件把它抽到 ``services/gemini/`` 一级模块，让 agent/ 的弃用清理与凭证加载脱钩。

    为兼容性，``agent/client.py`` 仍以 re-export 的方式暴露此符号；
    新代码请直接：

        from app.services.gemini.credentials import get_vertex_ai_credentials_from_db
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Tuple

import google.auth.exceptions as _google_auth_exc
import sqlalchemy.exc as _sa_exc

logger = logging.getLogger(__name__)

# Transient infrastructure errors that are safe to swallow: the caller will
# treat the result as "no configuration found" and fall back to ADC or reject
# the request explicitly. These are not credential-validity errors.
_TRANSIENT_INFRA_ERRORS = (
    _sa_exc.OperationalError,
    _google_auth_exc.TransportError,
)


def get_vertex_ai_credentials_from_db(
    user_id: str,
    db: Optional[Any] = None,
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[Any]]:
    """从数据库获取 Vertex AI 配置和 credentials（统一方法）。

    遵循与 ImagenCoordinator 和 ImageEditCoordinator 相同的模式：
      1. 查询 VertexAIConfig（不筛选 api_mode）
      2. 检查 api_mode 是否为 'vertex_ai'
      3. 解密 vertex_ai_credentials_json
      4. 创建 service_account.Credentials 对象

    Args:
        user_id: 用户 ID
        db: 数据库会话（SQLAlchemy Session）
        project: 可选的 project（如果提供，优先使用）
        location: 可选的 location（如果提供，优先使用）

    Returns:
        Tuple[project, location, credentials]:
          - project: Google Cloud 项目 ID（如果找到）
          - location: Google Cloud 位置（如果找到）
          - credentials: service_account.Credentials 对象（如果找到并成功解密），否则 None

    Raises:
        ValueError: credentials JSON is malformed (re-raised from JSONDecodeError) or
            from_service_account_info raised ValueError (invalid service-account structure).
        google.auth.exceptions.GoogleAuthError: non-transient OAuth/SDK error; caller
            must not silently fall back to ADC when credentials were explicitly configured.
    """
    if not db or not user_id:
        return None, None, None

    try:
        # 路径：app/services/gemini/credentials.py → 上 3 级到 app/，再进 models/ 或 core/
        from ...models.db_models import VertexAIConfig
        from ...core.encryption import decrypt_data

        # 查询 VertexAIConfig（不筛选 api_mode，与 ImagenCoordinator 保持一致）
        vertex_ai_config = db.query(VertexAIConfig).filter(
            VertexAIConfig.user_id == user_id
        ).first()

        if not vertex_ai_config:
            logger.debug(
                f"[get_vertex_ai_credentials_from_db] No VertexAIConfig found for user_id={user_id}"
            )
            return None, None, None

        if vertex_ai_config.api_mode != 'vertex_ai':
            logger.debug(
                f"[get_vertex_ai_credentials_from_db] VertexAIConfig exists but api_mode is "
                f"'{vertex_ai_config.api_mode}', not 'vertex_ai' (user_id={user_id})"
            )
            return None, None, None

        resolved_project = project or vertex_ai_config.vertex_ai_project_id
        resolved_location = location or vertex_ai_config.vertex_ai_location or 'us-central1'

        credentials = None
        credentials_json: Optional[str] = None
        if vertex_ai_config.vertex_ai_credentials_json:
            try:
                credentials_json = decrypt_data(vertex_ai_config.vertex_ai_credentials_json)

                from google.oauth2 import service_account
                credentials_info = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                logger.info(
                    f"[get_vertex_ai_credentials_from_db] Successfully loaded Vertex AI credentials "
                    f"from database (user_id={user_id})"
                )
                logger.debug(
                    f"[get_vertex_ai_credentials_from_db] Credentials type: {type(credentials).__name__}"
                )
            except json.JSONDecodeError as e:
                # JSON 解密失败必须 fail-fast：用户配的是 service account 但解密结果不是合法 JSON，
                # 静默 fallback ADC 会让请求以"错误身份"成功进入 GCP，是更危险的失败模式。
                logger.error(
                    f"[get_vertex_ai_credentials_from_db] Failed to parse credentials JSON "
                    f"(user_id={user_id}): {e}"
                )
                raise ValueError(
                    f"Vertex AI credentials JSON for user_id={user_id} is malformed; "
                    f"refusing to silently fallback to ADC. Please re-upload service-account JSON."
                ) from e
            except _TRANSIENT_INFRA_ERRORS as e:
                # 纯粹的瞬时基础设施故障（DB 短暂不可达、网络超时）：
                # 记录 ERROR 但允许调用方按"无配置"处理，避免短暂故障直接打挂业务。
                logger.error(
                    f"[get_vertex_ai_credentials_from_db] Transient infrastructure error while "
                    f"loading credentials (user_id={user_id}): {e}",
                    exc_info=True,
                )
            except Exception as e:
                # SDK / OAuth / 解密层错误（如 GoogleAuthError、ValueError from
                # from_service_account_info、加密层异常）：必须传播，禁止静默 fallback ADC，
                # 否则请求会以"错误身份"成功进入 GCP，是更危险的失败模式。
                logger.error(
                    f"[get_vertex_ai_credentials_from_db] Credential loading failed with a "
                    f"non-transient error (user_id={user_id}): {type(e).__name__}: {e}",
                    exc_info=True,
                )
                raise
        else:
            logger.info(
                f"[get_vertex_ai_credentials_from_db] No vertex_ai_credentials_json in database "
                f"(user_id={user_id}), will use ADC"
            )

        logger.info(
            f"[get_vertex_ai_credentials_from_db] Using Vertex AI config from database "
            f"(user_id={user_id}): project={resolved_project}, location={resolved_location}, "
            f"has_credentials={credentials is not None}"
        )

        return resolved_project, resolved_location, credentials

    except (ValueError, _google_auth_exc.GoogleAuthError):
        # ValueError: malformed JSON or invalid service-account structure.
        # GoogleAuthError (non-transient): OAuth/SDK error that must not be swallowed —
        # silently falling back to ADC when credentials were configured is a security risk
        # (the request would proceed as the wrong identity).
        raise
    except Exception as e:
        # 外层异常（DB 不可达 / import 失败 / 瞬时 OperationalError 等基础设施故障）：
        # 升级为 ERROR 级别，但仍返回 (None, None, None) —— 调用方按"无配置"处理（走 ADC 或拒绝），
        # 避免 DB 短暂故障直接打挂业务。
        logger.error(
            f"[get_vertex_ai_credentials_from_db] Failed to get Vertex AI config from database "
            f"(user_id={user_id}): {e}",
            exc_info=True,
        )
        return None, None, None


__all__ = ["get_vertex_ai_credentials_from_db"]
