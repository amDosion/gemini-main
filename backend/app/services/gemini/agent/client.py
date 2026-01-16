# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Official Google GenAI SDK Compatible Client Implementation

基于官方 google.genai.Client 的兼容层实现。
使用官方的 google.genai.Client 或 vertexai.Client，而不是自定义的 _interactions 实现。
"""

import asyncio
import os
import json
from types import TracebackType
from typing import Optional, Union, Tuple, Dict, Any
import logging

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

try:
    import vertexai
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    vertexai = None

from .types import HttpOptions, HttpOptionsDict

logger = logging.getLogger(__name__)


def get_vertex_ai_credentials_from_db(
    user_id: str,
    db: Optional[Any] = None,
    project: Optional[str] = None,
    location: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], Optional[Any]]:
    """
    从数据库获取 Vertex AI 配置和 credentials（统一方法）
    
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
    
    Example:
        >>> from app.core.database import get_db
        >>> db = next(get_db())
        >>> project, location, credentials = get_vertex_ai_credentials_from_db(
        ...     user_id="user123",
        ...     db=db
        ... )
        >>> if credentials:
        ...     client = Client(
        ...         vertexai=True,
        ...         project=project,
        ...         location=location,
        ...         credentials=credentials
        ...     )
    """
    if not db or not user_id:
        return None, None, None
    
    try:
        # 使用相对导入（从 app.services.gemini.agent.client 到 app.models 和 app.core）
        # 需要向上 4 级到 app/，然后进入 models/ 或 core/
        # 路径：app/services/gemini/agent/client.py -> app/models/db_models.py
        # 使用相对导入：....models.db_models（4个点表示向上4级）
        from ....models.db_models import VertexAIConfig
        from ....core.encryption import decrypt_data
        
        # 查询 VertexAIConfig（不筛选 api_mode，与 ImagenCoordinator 保持一致）
        vertex_ai_config = db.query(VertexAIConfig).filter(
            VertexAIConfig.user_id == user_id
        ).first()
        
        if not vertex_ai_config:
            logger.debug(f"[get_vertex_ai_credentials_from_db] No VertexAIConfig found for user_id={user_id}")
            return None, None, None
        
        # 检查 api_mode 是否为 vertex_ai
        if vertex_ai_config.api_mode != 'vertex_ai':
            logger.debug(
                f"[get_vertex_ai_credentials_from_db] VertexAIConfig exists but api_mode is "
                f"'{vertex_ai_config.api_mode}', not 'vertex_ai' (user_id={user_id})"
            )
            return None, None, None
        
        # 获取 project 和 location（如果没有提供）
        resolved_project = project or vertex_ai_config.vertex_ai_project_id
        resolved_location = location or vertex_ai_config.vertex_ai_location or 'us-central1'
        
        # 尝试获取并解密 service account credentials
        credentials = None
        if vertex_ai_config.vertex_ai_credentials_json:
            try:
                # 直接解密（decrypt_data 会自动处理加密/未加密的情况）
                credentials_json = decrypt_data(vertex_ai_config.vertex_ai_credentials_json)
                
                # 创建 credentials 对象
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
                logger.debug(f"[get_vertex_ai_credentials_from_db] Credentials type: {type(credentials).__name__}")
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
                    exc_info=True
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
            exc_info=True
        )
        return None, None, None
from .models import Models, AsyncModels
from .interactions import InteractionsResource, AsyncInteractionsResource

logger = logging.getLogger('google_genai.client')


class AsyncClient:
    """Client for making asynchronous (non-blocking) requests."""

    def __init__(self, client):
        """Initialize async client wrapper.
        
        Args:
            client: The underlying google.genai.Client instance
        """
        self._client = client
        self._models = AsyncModels(client)
        self._interactions = AsyncInteractionsResource(client)

    @property
    def models(self) -> AsyncModels:
        return self._models

    @property
    def interactions(self) -> AsyncInteractionsResource:
        return self._interactions

    async def aclose(self) -> None:
        """Closes the async client explicitly."""
        # Official SDK may not have aclose, so we check
        if hasattr(self._client, 'aclose'):
            await self._client.aclose()

    async def __aenter__(self) -> 'AsyncClient':
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Exception],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.aclose()


class Client:
    """Client for making synchronous requests.
    
    基于官方 google.genai.Client 的兼容层。
    支持 Vertex AI 和 Gemini API 两种模式。
    """

    def __init__(
        self,
        *,
        vertexai: Optional[bool] = None,
        api_key: Optional[str] = None,
        credentials = None,  # Service account credentials (for Vertex AI ADC mode)
        project: Optional[str] = None,
        location: Optional[str] = None,
        debug_config = None,
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None,
    ):
        """Initialize the client.
        
        Args:
            vertexai: Whether to use Vertex AI (default: False)
            api_key: Google API key (for Gemini API or Vertex AI Express mode)
            credentials: Google Cloud credentials (for Vertex AI)
            project: Google Cloud project ID (for Vertex AI)
            location: Google Cloud location (for Vertex AI, default: us-central1)
            debug_config: Debug configuration
            http_options: HTTP options (timeout, headers, etc.)
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google.genai package is not available. "
                "Please install it with: pip install google-genai"
            )
        
        # Store configuration
        self._vertexai = vertexai or False
        self._api_key = api_key or os.environ.get('GOOGLE_API_KEY')
        self._credentials = credentials
        self._project = project or os.environ.get('GOOGLE_CLOUD_PROJECT')
        self._location = location or os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Process HTTP options
        if isinstance(http_options, dict):
            http_options = HttpOptions(**http_options)
        self._http_options = http_options or HttpOptions()
        
        # Validate required parameters
        if not self._vertexai and not self._api_key:
            raise ValueError(
                'Missing API key! To use the Google AI API, '
                'provide api_key argument or set GOOGLE_API_KEY environment variable.'
            )
        
        if self._vertexai and not (self._project and self._location):
            # For Vertex AI Express mode, api_key is sufficient
            if not self._api_key:
                raise ValueError(
                    'Missing project or location! To use Vertex AI, '
                    'provide project and location arguments or set environment variables, '
                    'or provide api_key for Vertex AI Express mode.'
                )
        
        # Create official google.genai.Client
        client_kwargs = {}
        
        if self._vertexai:
            client_kwargs['vertexai'] = True
            # Vertex AI 模式：根据参考代码和错误信息，interactions API 需要：
            # 1. project 和 location（用于构建路径）
            # 2. OAuth2 credentials（不支持 API key）
            # 3. 需要先调用 vertexai.init() 初始化 Vertex AI SDK
            # 解决方案：使用 ADC（Application Default Credentials）或 service account credentials
            if self._project and self._location:
                # 初始化 Vertex AI SDK（参考 code_executor.py 和 memory_bank_service.py）
                # 注意：vertexai.init() 需要在创建 google.genai.Client 之前调用
                # 使用延迟导入，避免在模块级别导入失败
                try:
                    import vertexai as vertexai_module
                    vertexai_module.init(project=self._project, location=self._location)
                    logger.info(f"[Client] Initialized vertexai SDK: project={self._project}, location={self._location}")
                except ImportError:
                    logger.debug("[Client] vertexai module not available, skipping vertexai.init()")
                except Exception as e:
                    logger.warning(f"[Client] Failed to initialize vertexai SDK: {e}")
                    # 继续执行，google.genai.Client 可能仍然可以工作
                
                # 使用 project 和 location（用于构建路径）
                client_kwargs['project'] = self._project
                client_kwargs['location'] = self._location
                
                # 如果有 credentials（service account），使用它（推荐方式）
                if self._credentials:
                    client_kwargs['credentials'] = self._credentials
                    logger.info("[Client] Using Vertex AI with project/location and service account credentials")
                else:
                    # 使用 ADC（Application Default Credentials）
                    # 不传递 api_key，让 SDK 自动使用 ADC
                    # 需要环境中有 GOOGLE_APPLICATION_CREDENTIALS 或运行 gcloud auth application-default login
                    logger.info("[Client] Using Vertex AI ADC mode (project/location)")
                    logger.info("[Client] Make sure GOOGLE_APPLICATION_CREDENTIALS is set or run 'gcloud auth application-default login'")
            else:
                raise ValueError(
                    'For Vertex AI mode, project and location are required. '
                    'Please provide both project and location, and ensure ADC is configured '
                    '(GOOGLE_APPLICATION_CREDENTIALS environment variable or gcloud auth application-default login).'
                )
        else:
            # Gemini API 模式：只需要 api_key
            if self._api_key:
                client_kwargs['api_key'] = self._api_key
            else:
                raise ValueError('api_key is required for Gemini API mode')
        
        # Add HTTP options if provided
        if self._http_options:
            # Convert our HttpOptions to google.genai.types.HttpOptions
            try:
                from google.genai import types as genai_types
                genai_http_options = genai_types.HttpOptions()
                
                if hasattr(self._http_options, 'timeout') and self._http_options.timeout:
                    genai_http_options.timeout = self._http_options.timeout
                if hasattr(self._http_options, 'headers') and self._http_options.headers:
                    genai_http_options.headers = self._http_options.headers
                if hasattr(self._http_options, 'params') and self._http_options.params:
                    genai_http_options.params = self._http_options.params
                if hasattr(self._http_options, 'max_retries') and self._http_options.max_retries is not None:
                    genai_http_options.max_retries = self._http_options.max_retries
                
                client_kwargs['http_options'] = genai_http_options
            except ImportError:
                logger.warning("Could not import google.genai.types, http_options may not work correctly")
        
        # Create the official client
        self._genai_client = genai.Client(**client_kwargs)
        
        # 注意：Vertex AI 模式使用 ADC 或 credentials，不需要覆盖 prepare_options
        # 官方 SDK 会自动处理认证（使用 ADC 或传递的 credentials）
        
        # Initialize modules (wrappers around official client)
        self._aio = AsyncClient(self._genai_client)
        self._models = Models(self._genai_client)
        self._interactions = InteractionsResource(self._genai_client)

    @property
    def vertexai(self) -> bool:
        """Returns whether the client is using the Vertex AI API."""
        return self._vertexai

    @property
    def aio(self) -> AsyncClient:
        """Access to async client."""
        return self._aio

    @property
    def models(self) -> Models:
        """Access to models API."""
        return self._models

    @property
    def interactions(self) -> InteractionsResource:
        """Access to interactions API."""
        return self._interactions

    def close(self) -> None:
        """Closes the synchronous client explicitly."""
        if hasattr(self._genai_client, 'close'):
            self._genai_client.close()

    def __enter__(self) -> 'Client':
        return self

    def __exit__(
        self,
        exc_type: Optional[Exception],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()
