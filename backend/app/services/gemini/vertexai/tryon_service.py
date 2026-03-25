"""
Virtual Try-On 服务（独立版）

- 仅提供 recontext_image 虚拟试穿：人物图 + 服装图 → 结果图
- 与 GEN/Edit 统一：接收解密的 Vertex 配置（project_id, location, credentials_json），
  用 credentials 创建 Client；未传入时回退到 env / client_pool（兼容旧调用）
- 模型：virtual-try-on-001 / virtual-try-on-preview-08-04

掩码 / 编辑等已迁移至 mask_edit_service、expand_service、segmentation_service；
本模块不再保留兼容接口与掩码回退。
"""
import base64
import json
import logging
import os
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

from google.genai import types

logger = logging.getLogger(__name__)


@dataclass
class TryOnResult:
    """Try-On 结果"""
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mime_type: str = "image/png"
    error: Optional[str] = None


class TryOnService:
    """
    Virtual Try-On 服务（独立版）

    仅提供 recontext_image 虚拟试穿，人物图 + 服装图 → 结果图。
    与 GEN/Edit 统一：优先使用传入的解密 Vertex 配置创建客户端；
    未传入时回退到 env（GOOGLE_CLOUD_* / GCP_*）或 client_pool。
    """

    SUPPORTED_MODELS = {
        "virtual-try-on-001",
        "virtual-try-on-preview-08-04",
    }

    def __init__(self):
        pass

    def _clean_base64(self, data: str) -> str:
        """清理 Base64 前缀"""
        if data.startswith("data:"):
            return data.split(",", 1)[1]
        return data

    def _bytes_to_base64(self, data: bytes) -> str:
        return base64.b64encode(data).decode("utf-8")

    def _base64_to_bytes(self, data: str) -> bytes:
        return base64.b64decode(self._clean_base64(data))

    def _client_from_credentials(
        self,
        project_id: str,
        location: str,
        credentials_json: str,
    ):
        """
        使用解密的 credentials_json 创建 Vertex AI 客户端（与 ImagenCoordinator / VertexAIImageGenerator 一致）
        """
        from google.oauth2 import service_account
        from ..client_pool import get_client_pool

        info = json.loads(credentials_json)
        if info.get("type") != "service_account":
            raise ValueError("vertex_ai_credentials_json must be a service account JSON")

        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        pool = get_client_pool()
        client = pool.get_client(
            api_key=None,
            vertexai=True,
            project=project_id,
            location=location,
            credentials=credentials,
        )
        logger.debug(
            "[TryOnService] Retrieved Vertex client from unified pool: project=%s, location=%s",
            project_id,
            location,
        )
        return client

    def _client_from_env_or_pool(self) -> Tuple[Any, str, str]:
        """
        回退：从 env（GOOGLE_* / GCP_*）或 client_pool 获取客户端。
        返回 (client, project_id, location)。
        """
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GCP_LOCATION", "us-central1")
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

        if project_id and credentials_json:
            client = self._client_from_credentials(project_id, location, credentials_json)
            return client, project_id, location

        try:
            from ...core.config import settings
            project_id = project_id or settings.gcp_project_id
            location = location or (settings.gcp_location or "us-central1")
        except Exception as e:
            logger.warning("[TryOnService] config load failed: %s", e)

        if not project_id:
            raise ValueError(
                "Vertex AI not configured. Set GOOGLE_CLOUD_PROJECT / GCP_PROJECT_ID "
                "and GOOGLE_APPLICATION_CREDENTIALS_JSON, or user Vertex AI config."
            )

        from ..client_pool import get_client_pool
        pool = get_client_pool()
        client = pool.get_client(vertexai=True, project=project_id, location=location)
        logger.debug("[TryOnService] Using client_pool: project=%s, location=%s", project_id, location)
        return client, project_id, location

    def virtual_tryon(
        self,
        person_image_base64: str,
        clothing_image_base64: str,
        number_of_images: int = 1,
        output_mime_type: str = "image/jpeg",
        model: str = "virtual-try-on-001",
        *,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        credentials_json: Optional[str] = None,
        person_generation: Optional[Any] = None,
        base_steps: Optional[int] = None,
        output_compression_quality: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> TryOnResult:
        """
        虚拟试穿 - 使用 recontext_image API

        将服装穿在人物身上，无需掩码。
        优先使用传入的 project_id / location / credentials_json（与 GEN/Edit 统一传递解密的配置）；
        未传入时回退到 env 或 client_pool。

        官方支持的配置参数（来源: docs/virtual_try_on_sdk_usage_zh.md）:
        - number_of_images: 生成数量 (1-4)
        - base_steps: 质量步数（数值越高质量越好、延迟越高，如 8/16/32/48）
        - output_mime_type: 输出格式 (image/jpeg 推荐)
        - output_compression_quality: JPEG 压缩质量 (1-100，100 为最高质量)
        - seed: 随机种子

        Args:
            person_image_base64: Base64 编码的人物图像
            clothing_image_base64: Base64 编码的服装图像
            number_of_images: 生成图像数量 (1-4)
            output_mime_type: 输出格式（默认 image/jpeg）
            model: 模型 ID
            project_id: Vertex 项目 ID（可选，由路由统一解析后传入）
            location: Vertex 区域（可选）
            credentials_json: 解密的 service account JSON 字符串（可选）
            person_generation: PersonGeneration 枚举，默认 ALLOW_ALL，避免 "Adults only" 误拦
            base_steps: 质量步数（可选，数值越高质量越好）
            output_compression_quality: JPEG 压缩质量（可选，默认 100）
            seed: 随机种子（可选）

        Returns:
            TryOnResult
        """
        try:
            if model not in self.SUPPORTED_MODELS:
                logger.warning("[TryOnService] Model %s may not be supported", model)

            if project_id and location and credentials_json:
                client = self._client_from_credentials(project_id, location, credentials_json)
            else:
                client, _pid, _loc = self._client_from_env_or_pool()

            person_bytes = self._base64_to_bytes(person_image_base64)
            clothing_bytes = self._base64_to_bytes(clothing_image_base64)

            logger.info(
                "[TryOnService] Virtual try-on: model=%s, images=%s, base_steps=%s, quality=%s",
                model,
                number_of_images,
                base_steps,
                output_compression_quality,
            )

            # 构建配置参数（仅传入非 None 的值）
            config_kw: Dict[str, Any] = {
                "number_of_images": number_of_images,
                "output_mime_type": output_mime_type,
                "person_generation": person_generation
                if person_generation is not None
                else types.PersonGeneration.ALLOW_ALL,
            }
            
            # 可选参数：base_steps
            if base_steps is not None:
                config_kw["base_steps"] = base_steps
            
            # 可选参数：output_compression_quality（仅对 image/jpeg 有效）
            if output_compression_quality is not None and output_mime_type == "image/jpeg":
                config_kw["output_compression_quality"] = output_compression_quality
            
            # 可选参数：seed
            if seed is not None and seed >= 0:
                config_kw["seed"] = seed

            response = client.models.recontext_image(
                model=model,
                source=types.RecontextImageSource(
                    person_image=types.Image(image_bytes=person_bytes),
                    product_images=[
                        types.ProductImage(
                            product_image=types.Image(image_bytes=clothing_bytes),
                        )
                    ],
                ),
                config=types.RecontextImageConfig(**config_kw),
            )

            if response.generated_images and len(response.generated_images) > 0:
                result_image = response.generated_images[0].image
                result_base64 = self._bytes_to_base64(result_image.image_bytes)
                logger.info("[TryOnService] Virtual try-on successful")
                return TryOnResult(
                    success=True,
                    image=result_base64,
                    mime_type=output_mime_type,
                )
            return TryOnResult(success=False, error="No image generated")

        except Exception as e:
            error_msg = str(e)
            logger.error("[TryOnService] Virtual try-on error: %s", error_msg)
            return self._handle_error(error_msg)

    def _handle_error(self, error_msg: str) -> TryOnResult:
        """统一错误处理"""
        err = error_msg.upper()
        if "SAFETY" in err:
            return TryOnResult(
                success=False,
                error="Safety filter triggered. Please try different images.",
            )
        if "QUOTA" in err or "RESOURCE_EXHAUSTED" in err:
            return TryOnResult(
                success=False,
                error="API quota exceeded. Please try again later.",
            )
        if "PERMISSION" in err or "UNAUTHORIZED" in err:
            return TryOnResult(
                success=False,
                error="Authentication error. Please check Vertex AI credentials.",
            )
        if "only supported in the Vertex AI client" in error_msg.lower():
            return TryOnResult(
                success=False,
                error="This feature requires Vertex AI. Configure GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS_JSON or user Vertex AI settings.",
            )
        return TryOnResult(success=False, error=error_msg)

    def get_supported_models(self) -> list:
        return list(self.SUPPORTED_MODELS)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "supported_models": list(self.SUPPORTED_MODELS),
            "max_images": 4,
            "output_formats": ["image/jpeg", "image/png"],
            "requirements": {
                "person_image": "Full body image of a person",
                "clothing_image": "Single garment image (top, bottom, or full body)",
            },
            "config_options": {"number_of_images": "Number of variations to generate (1-4)"},
            "notes": [
                "Only supports 1 product image per request",
                "Product recontext supports up to 3 product images",
                "Requires Vertex AI (user config or GOOGLE_CLOUD_* / GCP_* env)",
            ],
        }


tryon_service = TryOnService()
