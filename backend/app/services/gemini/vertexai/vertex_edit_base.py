"""
Vertex AI 图像编辑共享基类

提供所有 Vertex AI 编辑服务的共享逻辑：
- 凭据绑定（构造函数接收 project_id, location, credentials_json）
- 懒加载客户端（_ensure_initialized）
- 配置构建（_build_config）
- 参考图像处理（_build_reference_images，支持 6 种类型）
- 响应处理（_process_response）
- 参数验证（validate_parameters）

所有 Vertex AI 编辑服务（InpaintingService、BackgroundEditService、
RecontextService、MaskEditService）都继承此基类，遵循与 gen 模式
（VertexAIImageGenerator）一致的有状态接口模式。
"""

import logging
import base64
import os
import re
import tempfile
from typing import Dict, Any, List, Optional

from ..base.image_edit_base import BaseImageEditor
from ..client_pool import get_client_pool
from ..base.image_edit_common import (
    decode_base64_image,
    validate_edit_mode,
    validate_reference_images,
    validate_number_of_images,
    validate_aspect_ratio,
    validate_guidance_scale,
    validate_output_mime_type,
    encode_image_to_base64,
    NotSupportedError,
    VALID_EDIT_MODES,
    VALID_REFERENCE_IMAGE_TYPES,
    VALID_ASPECT_RATIOS
)

logger = logging.getLogger(__name__)

# Default model for image editing
DEFAULT_EDIT_MODEL = 'imagen-3.0-capability-001'

# Import Google GenAI SDK
try:
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google.genai not available")


class VertexAIEditBase(BaseImageEditor):
    """
    Vertex AI 图像编辑共享基类

    提供统一的有状态接口模式：
    - 构造函数绑定凭据（与 VertexAIImageGenerator 一致）
    - 懒加载客户端
    - 统一的 edit_image() 接口
    - 返回 List[Dict[str, Any]]

    子类只需设置 DEFAULT_EDIT_MODE 即可自定义默认编辑模式。
    """

    # 子类可覆盖此属性以设置默认编辑模式
    DEFAULT_EDIT_MODE = None

    def __init__(
        self,
        project_id: str,
        location: str,
        credentials_json: str
    ):
        """
        Initialize Vertex AI edit service.

        Args:
            project_id: Google Cloud project ID
            location: Vertex AI location/region (e.g., 'us-central1')
            credentials_json: Service account credentials JSON content
        """
        if not GENAI_AVAILABLE:
            raise RuntimeError("google.genai not available. Install with: pip install google-genai")

        self.project_id = project_id
        self.location = location
        self.credentials_json = credentials_json
        self._client = None
        self._initialized = False

        # Validate credentials JSON
        import json
        try:
            self.credentials_info = json.loads(credentials_json)
            if 'type' not in self.credentials_info or self.credentials_info['type'] != 'service_account':
                raise ValueError("Invalid service account JSON: missing 'type' field or not a service account")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

        logger.info(f"[{self.__class__.__name__}] Initialized with project={project_id}, location={location}")

    def _ensure_initialized(self):
        """Ensure client is initialized (lazy loading)."""
        if self._initialized:
            return

        try:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_info(
                self.credentials_info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )

            pool = get_client_pool()
            pooled_client = pool.get_client(
                api_key=None,
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=credentials
            )
            # Vertex edit APIs need raw google.genai.Client methods.
            self._client = getattr(pooled_client, "_genai_client", pooled_client)
            self._initialized = True
            logger.info(f"[{self.__class__.__name__}] Client initialized from unified pool")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Failed to initialize client: {e}")
            raise RuntimeError(f"Failed to initialize Vertex AI client: {e}")

    def edit_image(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Edit images using Vertex AI.

        Args:
            prompt: Text description of the desired edit
            reference_images: Dictionary mapping reference image types to Base64 strings
            config: Optional configuration dictionary

        Returns:
            List of dictionaries containing edited image data with metadata
        """
        self._ensure_initialized()
        self.validate_parameters(prompt, reference_images, config)

        logger.info(f"[{self.__class__.__name__}] Editing image: prompt={prompt[:50]}...")

        # Config from middleware is already in snake_case
        effective_config = config or {}

        # Merge default edit_mode if not provided
        if self.DEFAULT_EDIT_MODE and 'edit_mode' not in effective_config:
            effective_config['edit_mode'] = self.DEFAULT_EDIT_MODE

        # Build configuration
        edit_config = self._build_config(effective_config)

        # Build reference images
        ref_images = self._build_reference_images(reference_images, effective_config)

        # Get model from config
        model = effective_config.get('model', DEFAULT_EDIT_MODEL)
        logger.info(f"[{self.__class__.__name__}] Using model: {model}")

        try:
            response = self._client.models.edit_image(
                model=model,
                prompt=prompt,
                reference_images=ref_images,
                config=edit_config
            )

            if not response.generated_images:
                raise RuntimeError("No images generated")

            return self._process_response(response, effective_config)

        except Exception as e:
            error_msg = str(e)
            if 'data:image' in error_msg or 'base64' in error_msg.lower():
                error_msg = re.sub(r'data:image[^,]+,\s*[A-Za-z0-9+/]{100,}', 'data:image/...base64...[TRUNCATED]', error_msg)
            logger.error(f"[{self.__class__.__name__}] Editing failed: {error_msg}")

            # Classified error handling
            error_upper = error_msg.upper()
            if "SAFETY" in error_upper:
                raise RuntimeError("Safety filter triggered. Please modify your prompt or image.")
            elif "QUOTA" in error_upper or "RESOURCE_EXHAUSTED" in error_upper:
                raise RuntimeError("API quota exceeded. Please try again later.")
            elif "PERMISSION" in error_upper or "UNAUTHORIZED" in error_upper:
                raise RuntimeError("Authentication error. Please check GCP credentials.")
            elif "only supported in the vertex ai client" in error_msg.lower():
                raise RuntimeError("This feature requires Vertex AI mode. Please configure GCP credentials.")
            else:
                raise RuntimeError(f"Image editing failed: {error_msg}")

    def _build_config(self, config: Dict[str, Any]) -> 'genai_types.EditImageConfig':
        """Build Vertex AI EditImageConfig from parameters.

        All parameters are expected in snake_case format (middleware handles camelCase conversion).
        """
        config_kwargs = {}

        # Edit mode
        edit_mode = config.get('edit_mode')
        if edit_mode:
            if edit_mode.startswith('EDIT_MODE_'):
                try:
                    config_kwargs['edit_mode'] = getattr(genai_types.EditMode, edit_mode)
                except AttributeError:
                    logger.warning(f"[{self.__class__.__name__}] Unknown edit_mode: {edit_mode}, skipping")
            else:
                mode_map = {
                    'inpainting-insert': genai_types.EditMode.EDIT_MODE_INPAINT_INSERTION,
                    'inpainting-remove': genai_types.EditMode.EDIT_MODE_INPAINT_REMOVAL,
                    'outpainting': genai_types.EditMode.EDIT_MODE_OUTPAINT,
                    'product-image': genai_types.EditMode.EDIT_MODE_PRODUCT_IMAGE,
                    'mask_edit': genai_types.EditMode.EDIT_MODE_INPAINT_INSERTION,
                    'inpainting': genai_types.EditMode.EDIT_MODE_INPAINT_INSERTION,
                    'background_edit': genai_types.EditMode.EDIT_MODE_BGSWAP,
                    'recontext': genai_types.EditMode.EDIT_MODE_INPAINT_INSERTION,
                }
                if edit_mode in mode_map:
                    config_kwargs['edit_mode'] = mode_map[edit_mode]
                else:
                    logger.warning(f"[{self.__class__.__name__}] Unknown edit_mode: {edit_mode}, skipping")

        # Number of images
        number_of_images = config.get('number_of_images', 1)
        config_kwargs['number_of_images'] = min(max(int(number_of_images), 1), 4)

        # Aspect ratio
        aspect_ratio = config.get('aspect_ratio')
        if aspect_ratio:
            config_kwargs['aspect_ratio'] = aspect_ratio

        # Guidance scale (use None-safe lookup to avoid 0 being falsy)
        guidance_scale = config.get('guidance_scale')
        if guidance_scale is not None:
            config_kwargs['guidance_scale'] = float(guidance_scale)

        # Output MIME type
        output_mime_type = config.get('output_mime_type', 'image/jpeg')
        config_kwargs['output_mime_type'] = output_mime_type

        # Negative prompt
        negative_prompt = config.get('negative_prompt')
        if negative_prompt:
            config_kwargs['negative_prompt'] = negative_prompt

        # Output compression quality
        # IMPORTANT: PNG does not accept compressionQuality — only set for JPEG
        output_compression_quality = config.get('output_compression_quality')
        if output_compression_quality is not None and output_mime_type == 'image/jpeg':
            config_kwargs['output_compression_quality'] = int(output_compression_quality)

        # Safety filter level (supports both lowercase aliases and SDK enum names)
        safety_filter_level = config.get('safety_filter_level')
        if safety_filter_level:
            # Lowercase alias → SDK enum name (lazy mapping, avoids AttributeError at definition time)
            safety_alias_map = {
                'block_most': 'BLOCK_LOW_AND_ABOVE',
                'block_some': 'BLOCK_MEDIUM_AND_ABOVE',
                'block_few': 'BLOCK_ONLY_HIGH',
                'block_fewest': 'BLOCK_NONE',
            }
            sdk_name = safety_alias_map.get(safety_filter_level, safety_filter_level)
            if hasattr(genai_types.SafetyFilterLevel, sdk_name):
                config_kwargs['safety_filter_level'] = getattr(genai_types.SafetyFilterLevel, sdk_name)
            else:
                logger.warning(f"[{self.__class__.__name__}] Unknown safety_filter_level: {safety_filter_level}, skipping")

        # Person generation (supports both lowercase aliases and SDK enum names)
        person_generation = config.get('person_generation')
        if person_generation:
            person_alias_map = {
                'dont_allow': 'DONT_ALLOW',
                'allow_adult': 'ALLOW_ADULT',
                'allow_all': 'ALLOW_ALL',
            }
            sdk_name = person_alias_map.get(person_generation, person_generation)
            if hasattr(genai_types.PersonGeneration, sdk_name):
                config_kwargs['person_generation'] = getattr(genai_types.PersonGeneration, sdk_name)
            else:
                logger.warning(f"[{self.__class__.__name__}] Unknown person_generation: {person_generation}, skipping")

        # Include RAI reason
        config_kwargs['include_rai_reason'] = config.get('include_rai_reason', True)

        logger.info(f"[{self.__class__.__name__}] Config: {config_kwargs}")

        return genai_types.EditImageConfig(**config_kwargs)

    def _build_reference_images(self, reference_images: Dict[str, str], config: Optional[Dict[str, Any]] = None) -> List:
        """
        Build reference image objects for Vertex AI.

        Supports 6 reference image types:
        - raw: Base image to edit
        - mask: Mask for inpainting (user-provided mask image)
        - control: Control image for guided generation
        - style: Style reference
        - subject: Subject reference
        - content: Content reference

        Also supports auto-mask mode when config contains 'mask_mode'.
        """
        config = config or {}
        ref_images = []
        reference_id = 1
        has_mask_ref = False

        for ref_type, base64_data in reference_images.items():
            if isinstance(base64_data, dict):
                base64_data = base64_data.get('url', '')
            if isinstance(base64_data, str) and base64_data.startswith('data:'):
                base64_data = base64_data.split(',', 1)[-1] if ',' in base64_data else base64_data

            image_bytes = decode_base64_image(base64_data)

            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            try:
                image = genai_types.Image.from_file(location=tmp_path)

                if ref_type == 'raw':
                    ref_image = genai_types.RawReferenceImage(
                        reference_id=reference_id,
                        reference_image=image
                    )
                elif ref_type == 'mask':
                    mask_dilation = config.get('mask_dilation', 0.06)
                    ref_image = genai_types.MaskReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.MaskReferenceConfig(
                            mask_mode='MASK_MODE_USER_PROVIDED',
                            mask_dilation=float(mask_dilation)
                        )
                    )
                    has_mask_ref = True
                elif ref_type == 'control':
                    ref_image = genai_types.ControlReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.ControlReferenceConfig(
                            control_type='CONTROL_TYPE_SCRIBBLE',
                            enable_control_image_computation=False
                        )
                    )
                elif ref_type == 'style':
                    ref_image = genai_types.StyleReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.StyleReferenceConfig(
                            style_description='style reference'
                        )
                    )
                elif ref_type == 'subject':
                    ref_image = genai_types.SubjectReferenceImage(
                        reference_id=reference_id,
                        reference_image=image,
                        config=genai_types.SubjectReferenceConfig(
                            subject_type='SUBJECT_TYPE_PRODUCT',
                            subject_description='subject reference'
                        )
                    )
                elif ref_type == 'content':
                    ref_image = genai_types.ContentReferenceImage(
                        reference_id=reference_id,
                        reference_image=image
                    )
                else:
                    logger.warning(f"[{self.__class__.__name__}] Unknown reference type: {ref_type}")
                    continue

                ref_images.append(ref_image)
                reference_id += 1

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        # Auto-mask mode
        if not has_mask_ref:
            mask_mode = config.get('mask_mode')
            if mask_mode:
                mask_dilation = config.get('mask_dilation', 0.06)
                mask_config_kwargs = {
                    'mask_mode': mask_mode,
                    'mask_dilation': float(mask_dilation),
                }
                if mask_mode == 'MASK_MODE_SEMANTIC':
                    seg_classes = config.get('segmentation_classes')
                    if seg_classes:
                        mask_config_kwargs['segmentation_classes'] = seg_classes

                auto_mask = genai_types.MaskReferenceImage(
                    reference_id=reference_id,
                    config=genai_types.MaskReferenceConfig(**mask_config_kwargs)
                )
                ref_images.append(auto_mask)
                reference_id += 1
                logger.info(f"[{self.__class__.__name__}] Added auto-mask: mode={mask_mode}, dilation={mask_dilation}")

        logger.info(f"[{self.__class__.__name__}] Built {len(ref_images)} reference images")
        return ref_images

    def _process_response(self, response, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process Vertex AI response and extract edited images."""
        output_mime_type = config.get('output_mime_type', 'image/jpeg')
        results = []

        for idx, generated_image in enumerate(response.generated_images):
            if hasattr(generated_image, 'rai_filtered_reason') and generated_image.rai_filtered_reason:
                logger.warning(f"[{self.__class__.__name__}] Image {idx} filtered: {generated_image.rai_filtered_reason}")
                continue

            if not generated_image.image:
                continue

            if not hasattr(generated_image.image, 'image_bytes') or generated_image.image.image_bytes is None:
                logger.warning(f"[{self.__class__.__name__}] Image {idx} has no image_bytes")
                continue

            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                generated_image.image.save(tmp_path)
                with open(tmp_path, 'rb') as f:
                    image_bytes = f.read()
                b64_data = encode_image_to_base64(image_bytes)

                result = {
                    "url": f"data:{output_mime_type};base64,{b64_data}",
                    "mime_type": output_mime_type,
                    "index": idx,
                    "size": len(image_bytes)
                }

                enhanced_prompt_value = None
                if hasattr(generated_image, 'enhanced_prompt') and generated_image.enhanced_prompt:
                    enhanced_prompt_value = generated_image.enhanced_prompt
                elif hasattr(generated_image, 'prompt') and generated_image.prompt:
                    enhanced_prompt_value = generated_image.prompt

                if enhanced_prompt_value:
                    result["enhanced_prompt"] = enhanced_prompt_value

                results.append(result)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        if not results:
            filtered_count = sum(
                1 for img in response.generated_images
                if hasattr(img, 'rai_filtered_reason') and img.rai_filtered_reason
            )
            if filtered_count > 0:
                first_reason = next(
                    (img.rai_filtered_reason for img in response.generated_images
                     if hasattr(img, 'rai_filtered_reason') and img.rai_filtered_reason),
                    "Unknown reason"
                )
                raise RuntimeError(f"All images filtered by content policy: {first_reason}")
            else:
                raise RuntimeError("No valid images generated")

        logger.info(f"[{self.__class__.__name__}] Generated {len(results)} edited images")
        return results

    def validate_parameters(
        self,
        prompt: str,
        reference_images: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Validate edit parameters."""
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt must be a non-empty string")

        validate_reference_images(reference_images)

        if config:
            edit_mode = config.get('edit_mode')
            validate_edit_mode(edit_mode)

            number_of_images = config.get('number_of_images')
            validate_number_of_images(number_of_images)

            aspect_ratio = config.get('aspect_ratio')
            validate_aspect_ratio(aspect_ratio)

            guidance_scale = config.get('guidance_scale')
            validate_guidance_scale(guidance_scale)

            output_mime_type = config.get('output_mime_type')
            validate_output_mime_type(output_mime_type)


    def get_capabilities(self) -> Dict[str, Any]:
        """Get Vertex AI image editing capabilities."""
        return {
            'api_type': 'vertex_ai',
            'supports_editing': True,
            'supported_edit_modes': VALID_EDIT_MODES,
            'supported_reference_types': VALID_REFERENCE_IMAGE_TYPES,
            'max_images': 4,
            'aspect_ratios': VALID_ASPECT_RATIOS,
            'guidance_scale_range': (0, 100)
        }

    def get_supported_models(self) -> List[str]:
        """Get supported Imagen models for editing."""
        return [
            'imagen-3.0-capability-001',
            'imagen-4.0-ingredients-preview'
        ]
