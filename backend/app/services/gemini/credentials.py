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

logger = logging.getLogger(__name__)


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
                logger.error(
                    f"[get_vertex_ai_credentials_from_db] Failed to parse credentials JSON "
                    f"(user_id={user_id}): {e}"
                )
                logger.debug(
                    f"[get_vertex_ai_credentials_from_db] Credentials JSON (first 100 chars): "
                    f"{credentials_json[:100] if credentials_json else 'None'}"
                )
            except Exception as e:
                logger.warning(
                    f"[get_vertex_ai_credentials_from_db] Failed to load credentials from database "
                    f"(user_id={user_id}): {e}",
                    exc_info=True,
                )
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

    except Exception as e:
        logger.warning(
            f"[get_vertex_ai_credentials_from_db] Failed to get Vertex AI config from database "
            f"(user_id={user_id}): {e}",
            exc_info=True,
        )
        return None, None, None


__all__ = ["get_vertex_ai_credentials_from_db"]
