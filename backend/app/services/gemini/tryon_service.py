"""
Virtual Try-On 服务
封装 Vertex AI Imagen 3 API 调用逻辑

支持两种模式：
1. Vertex AI 模式：使用 GCP 项目认证，调用 Imagen 3 API
2. Gemini API 模式：使用 API Key，调用 Gemini 图像编辑 API（备用方案）
"""
import base64
import io
import os
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

# 尝试导入 Vertex AI SDK
try:
    from google.cloud import aiplatform
    from vertexai.preview.vision_models import ImageGenerationModel, Image as VertexImage
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("[TryOnService] Vertex AI SDK not available, will use Gemini API fallback")

# 尝试导入 Gemini SDK（备用方案）
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[TryOnService] Google GenAI SDK not available")


def validate_image(image_base64: str) -> Tuple[bool, str]:
    """
    验证图像格式和大小
    
    Args:
        image_base64: Base64 编码的图像
    
    Returns:
        (is_valid, error_message)
    """
    try:
        from PIL import Image as PILImage
        
        # 清理 Base64 前缀
        if image_base64.startswith('data:'):
            image_base64 = image_base64.split(',', 1)[1]
        
        # 解码 Base64
        image_bytes = base64.b64decode(image_base64)
        
        # 检查文件大小（10MB）
        MAX_SIZE_MB = 10
        if len(image_bytes) > MAX_SIZE_MB * 1024 * 1024:
            return False, f"图像文件超过 {MAX_SIZE_MB}MB 限制"
        
        # 检查图像格式
        img = PILImage.open(io.BytesIO(image_bytes))
        if img.format not in ['PNG', 'JPEG']:
            return False, "仅支持 PNG 和 JPEG 格式"
        
        return True, ""
    except Exception as e:
        return False, f"图像验证失败: {str(e)}"


@dataclass
class TryOnResult:
    """Try-On 结果"""
    success: bool
    image: Optional[str] = None  # Base64 编码的结果图
    mime_type: str = "image/png"
    error: Optional[str] = None


class TryOnService:
    """Virtual Try-On 服务"""

    def __init__(self):
        self._vertex_initialized = False
        self._project_id = None
        self._location = None

    def _init_vertex_ai(self) -> bool:
        """初始化 Vertex AI"""
        if not VERTEX_AI_AVAILABLE:
            return False

        if self._vertex_initialized:
            return True

        try:
            from ...core.config import settings
            
            if not settings.gcp_project_id:
                print("[TryOnService] GCP_PROJECT_ID not configured")
                return False

            self._project_id = settings.gcp_project_id
            self._location = settings.gcp_location

            aiplatform.init(
                project=self._project_id,
                location=self._location
            )
            self._vertex_initialized = True
            print(f"[TryOnService] Vertex AI initialized: project={self._project_id}, location={self._location}")
            return True

        except Exception as e:
            print(f"[TryOnService] Failed to initialize Vertex AI: {e}")
            return False

    def edit_with_mask_vertex(
        self,
        image_base64: str,
        mask_base64: str,
        prompt: str,
        edit_mode: str = "inpainting-insert",
        mask_mode: str = "foreground",
        dilation: float = 0.02
    ) -> TryOnResult:
        """
        使用 Vertex AI Imagen 3 进行掩码编辑
        
        Args:
            image_base64: Base64 编码的原图（不含 data:image/xxx;base64, 前缀）
            mask_base64: Base64 编码的掩码（不含前缀）
            prompt: 服装描述
            edit_mode: 编辑模式（inpainting-insert/inpainting-remove）
            mask_mode: 掩码模式（foreground/background）
            dilation: 掩码膨胀系数
        
        Returns:
            TryOnResult
        """
        if not self._init_vertex_ai():
            return TryOnResult(
                success=False,
                error="Vertex AI not available or not configured"
            )

        try:
            # 解码图像
            image_bytes = base64.b64decode(image_base64)
            mask_bytes = base64.b64decode(mask_base64)

            # 创建 Vertex AI Image 对象
            base_image = VertexImage(image_bytes=image_bytes)
            mask_image = VertexImage(image_bytes=mask_bytes)

            # 加载编辑模型
            edit_model = ImageGenerationModel.from_pretrained("imagen-3.0-capability-001")

            # 执行编辑
            print(f"[TryOnService] Editing with Vertex AI: mode={edit_mode}, prompt={prompt[:50]}...")
            
            response = edit_model.edit_image(
                prompt=prompt,
                base_image=base_image,
                mask=mask_image,
                edit_mode=edit_mode,
                mask_mode=mask_mode,
                mask_dilation=dilation,
                number_of_images=1,
                person_generation="allow_adult"
            )

            if response.images and len(response.images) > 0:
                result_image = response.images[0]
                result_bytes = result_image._image_bytes
                result_base64 = base64.b64encode(result_bytes).decode('utf-8')
                
                print(f"[TryOnService] Edit successful, result size: {len(result_bytes)} bytes")
                return TryOnResult(
                    success=True,
                    image=result_base64,
                    mime_type="image/png"
                )
            else:
                return TryOnResult(
                    success=False,
                    error="No image generated"
                )

        except Exception as e:
            error_msg = str(e)
            print(f"[TryOnService] Vertex AI edit error: {error_msg}")
            
            # 检查常见错误
            if "SAFETY" in error_msg.upper():
                return TryOnResult(success=False, error="Safety filter triggered. Please modify your prompt.")
            elif "QUOTA" in error_msg.upper() or "RESOURCE_EXHAUSTED" in error_msg:
                return TryOnResult(success=False, error="API quota exceeded. Please try again later.")
            elif "PERMISSION" in error_msg.upper() or "UNAUTHORIZED" in error_msg.upper():
                return TryOnResult(success=False, error="Authentication error. Please check GCP credentials.")
            else:
                return TryOnResult(success=False, error=error_msg)

    def edit_with_gemini(
        self,
        image_base64: str,
        prompt: str,
        api_key: str,
        target_clothing: str = "upper body clothing"
    ) -> TryOnResult:
        """
        使用 Gemini API 进行图像编辑（备用方案）
        
        不需要掩码，直接让 Gemini 理解并编辑图像
        
        Args:
            image_base64: Base64 编码的原图
            prompt: 服装描述
            api_key: Gemini API Key
            target_clothing: 目标服装类型
        
        Returns:
            TryOnResult
        """
        if not GENAI_AVAILABLE:
            return TryOnResult(
                success=False,
                error="Google GenAI SDK not available"
            )

        try:
            # 创建客户端
            client = genai.Client(api_key=api_key)

            # 构建编辑 prompt
            edit_prompt = f"""Perform a virtual try-on editing task on this image.
Identify the {target_clothing} worn by the person.
Replace ONLY the {target_clothing} with: {prompt}
Keep the person's face, pose, body shape, and background EXACTLY the same.
The new clothing should match the lighting and style of the original image."""

            # 准备图像数据
            image_data = base64.b64decode(image_base64)

            # 调用 Gemini 图像编辑
            print(f"[TryOnService] Editing with Gemini API: target={target_clothing}, prompt={prompt[:50]}...")
            
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    {
                        "parts": [
                            {"inline_data": {"mime_type": "image/png", "data": image_base64}},
                            {"text": edit_prompt}
                        ]
                    }
                ],
                config={
                    "response_modalities": ["TEXT", "IMAGE"]
                }
            )

            # 提取结果图像
            if response.candidates and len(response.candidates) > 0:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        result_base64 = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "image/png"
                        print(f"[TryOnService] Gemini edit successful")
                        return TryOnResult(
                            success=True,
                            image=result_base64,
                            mime_type=mime_type
                        )

            return TryOnResult(
                success=False,
                error="No image generated by Gemini"
            )

        except Exception as e:
            error_msg = str(e)
            print(f"[TryOnService] Gemini edit error: {error_msg}")
            return TryOnResult(success=False, error=error_msg)

    def edit_with_mask(
        self,
        image_base64: str,
        mask_base64: Optional[str],
        prompt: str,
        edit_mode: str = "inpainting-insert",
        mask_mode: str = "foreground",
        dilation: float = 0.02,
        api_key: Optional[str] = None,
        target_clothing: str = "upper body clothing"
    ) -> TryOnResult:
        """
        统一的编辑接口
        
        优先使用 Vertex AI，如果不可用则回退到 Gemini API
        
        Args:
            image_base64: Base64 编码的原图
            mask_base64: Base64 编码的掩码（可选，Gemini 模式不需要）
            prompt: 服装描述
            edit_mode: 编辑模式
            mask_mode: 掩码模式
            dilation: 掩码膨胀系数
            api_key: Gemini API Key（用于备用方案）
            target_clothing: 目标服装类型
        
        Returns:
            TryOnResult
        """
        # 清理 Base64 前缀
        if image_base64.startswith('data:'):
            image_base64 = image_base64.split(',', 1)[1]
        if mask_base64 and mask_base64.startswith('data:'):
            mask_base64 = mask_base64.split(',', 1)[1]

        # 尝试 Vertex AI
        if VERTEX_AI_AVAILABLE and mask_base64:
            result = self.edit_with_mask_vertex(
                image_base64=image_base64,
                mask_base64=mask_base64,
                prompt=prompt,
                edit_mode=edit_mode,
                mask_mode=mask_mode,
                dilation=dilation
            )
            if result.success:
                return result
            print(f"[TryOnService] Vertex AI failed: {result.error}, trying Gemini fallback...")

        # 回退到 Gemini API
        if api_key:
            return self.edit_with_gemini(
                image_base64=image_base64,
                prompt=prompt,
                api_key=api_key,
                target_clothing=target_clothing
            )

        return TryOnResult(
            success=False,
            error="No available editing backend. Configure Vertex AI or provide Gemini API key."
        )
    
    async def virtual_tryon(
        self,
        prompt: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> TryOnResult:
        """
        统一的虚拟试穿接口 - 处理参数提取
        
        Args:
            prompt: 服装描述
            reference_images: 参考图片字典 {'raw': image_base64, 'mask': mask_base64}
            **kwargs: 额外参数：
                - edit_mode: 编辑模式
                - mask_mode: 掩码模式
                - dilation: 掩码膨胀系数
                - api_key: Gemini API Key
                - target_clothing: 目标服装类型
        
        Returns:
            TryOnResult
        """
        # 从 reference_images 或 kwargs 中提取图片
        image_base64 = None
        mask_base64 = None
        
        if reference_images:
            image_base64 = reference_images.get("raw")
            mask_base64 = reference_images.get("mask")
        else:
            # 兼容旧接口：从 kwargs 中提取
            image_base64 = kwargs.get("image_base64")
            mask_base64 = kwargs.get("mask_base64")
        
        if not image_base64:
            raise ValueError("virtual_tryon requires 'raw' image in reference_images or 'image_base64' in kwargs")
        
        edit_mode = kwargs.get("edit_mode", "inpainting-insert")
        mask_mode = kwargs.get("mask_mode", "foreground")
        dilation = kwargs.get("dilation", 0.02)
        api_key = kwargs.get("api_key")
        target_clothing = kwargs.get("target_clothing", "upper body clothing")
        
        return self.edit_with_mask(
            image_base64=image_base64,
            mask_base64=mask_base64,
            prompt=prompt,
            edit_mode=edit_mode,
            mask_mode=mask_mode,
            dilation=dilation,
            api_key=api_key,
            target_clothing=target_clothing
        )

    def upscale_image(
        self,
        image_base64: str,
        upscale_factor: int = 2,
        add_watermark: bool = False
    ) -> TryOnResult:
        """
        使用 Imagen 4 进行图像超分辨率
        
        Args:
            image_base64: Base64 编码的原图
            upscale_factor: 放大倍数（2 或 4）
            add_watermark: 是否添加水印
        
        Returns:
            TryOnResult
        """
        if not self._init_vertex_ai():
            return TryOnResult(
                success=False,
                error="Vertex AI not available or not configured"
            )

        try:
            from PIL import Image as PILImage
            
            # 解码图像
            image_bytes = base64.b64decode(image_base64)
            
            # 检查原始分辨率
            img = PILImage.open(io.BytesIO(image_bytes))
            original_width, original_height = img.size
            original_resolution = f"{original_width}x{original_height}"
            
            # 计算输出分辨率
            new_width = original_width * upscale_factor
            new_height = original_height * upscale_factor
            new_megapixels = (new_width * new_height) / 1_000_000
            upscaled_resolution = f"{new_width}x{new_height}"
            
            # 检查分辨率限制（17MP）
            MAX_MEGAPIXELS = 17
            if new_megapixels > MAX_MEGAPIXELS:
                return TryOnResult(
                    success=False,
                    error=f"Output resolution {new_megapixels:.2f}MP exceeds limit {MAX_MEGAPIXELS}MP. Original: {original_resolution}, Target: {upscaled_resolution}"
                )
            
            # 创建 Vertex AI Image 对象
            base_image = VertexImage(image_bytes=image_bytes)
            
            # 加载 Upscale 模型
            upscale_model = ImageGenerationModel.from_pretrained("imagen-4.0-upscale-preview")
            
            # 执行超分辨率
            print(f"[TryOnService] Upscaling with Imagen 4: {original_resolution} -> {upscaled_resolution} ({upscale_factor}x)")
            
            response = upscale_model.upscale_image(
                image=base_image,
                upscale_factor=upscale_factor,
                add_watermark=add_watermark
            )
            
            if response.images and len(response.images) > 0:
                result_image = response.images[0]
                result_bytes = result_image._image_bytes
                result_base64 = base64.b64encode(result_bytes).decode('utf-8')
                
                print(f"[TryOnService] Upscale successful, result size: {len(result_bytes)} bytes")
                return TryOnResult(
                    success=True,
                    image=result_base64,
                    mime_type="image/png"
                )
            else:
                return TryOnResult(
                    success=False,
                    error="No upscaled image generated"
                )
        
        except Exception as e:
            error_msg = str(e)
            print(f"[TryOnService] Upscale error: {error_msg}")
            
            # 检查常见错误
            if "QUOTA" in error_msg.upper() or "RESOURCE_EXHAUSTED" in error_msg:
                return TryOnResult(success=False, error="API quota exceeded. Please try again later.")
            elif "PERMISSION" in error_msg.upper() or "UNAUTHORIZED" in error_msg.upper():
                return TryOnResult(success=False, error="Authentication error. Please check GCP credentials.")
            else:
                return TryOnResult(success=False, error=error_msg)


    async def segment_clothing(
        self,
        image_base64: str,
        target_clothing: str,
        model: str = "gemini-2.0-flash-exp",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用 Gemini API 进行服装区域分割
        
        Args:
            image_base64: Base64 编码的图像
            target_clothing: 目标服装类型（如 "upper body clothing", "lower body clothing"）
            model: Gemini 模型 ID（默认: gemini-2.0-flash-exp）
            api_key: Gemini API Key（如果未提供，需要从配置中获取）
        
        Returns:
            Dict with segmentation results:
                - success: Boolean
                - segments: List of segmentation results
                - error: Error message (if failed)
        """
        if not GENAI_AVAILABLE:
            return {
                "success": False,
                "error": "Google GenAI SDK not available"
            }
        
        if not api_key:
            return {
                "success": False,
                "error": "API key is required for clothing segmentation"
            }
        
        try:
            # 清理 Base64 前缀
            if image_base64.startswith('data:'):
                image_base64 = image_base64.split(',', 1)[1]
            
            # 创建客户端
            client = genai.Client(api_key=api_key)
            
            # 构建分割 prompt
            segment_prompt = f"""Give the segmentation masks for {target_clothing} in this image.
Output a JSON list of segmentation masks where each entry contains:
- the 2D bounding box in the key 'box_2d' as [y0, x0, y1, x1] normalized to 1000
- the segmentation mask in key 'mask' as a base64 encoded PNG image (data:image/png;base64,...)
- the text label in the key 'label'

Only output the JSON array, no other text or markdown formatting."""
            
            print(f"[TryOnService] Segmenting clothing: target={target_clothing}, model={model}")
            
            # 调用 Gemini API
            response = client.models.generate_content(
                model=model,
                contents=[
                    {
                        "parts": [
                            {"inline_data": {"mime_type": "image/png", "data": image_base64}},
                            {"text": segment_prompt}
                        ]
                    }
                ]
            )
            
            # 解析响应
            if response.candidates and len(response.candidates) > 0:
                text = response.candidates[0].content.parts[0].text
                
                # 清理可能的 markdown 代码块
                json_text = text.strip()
                if json_text.startswith('```'):
                    lines = json_text.split('\n')
                    lines.pop(0)  # 移除 ```json
                    if lines and lines[-1] == '```':
                        lines.pop()
                    json_text = '\n'.join(lines)
                
                import json
                segments_data = json.loads(json_text)
                
                print(f"[TryOnService] Segmentation successful: {len(segments_data)} segments found")
                return {
                    "success": True,
                    "segments": segments_data
                }
            
            return {
                "success": False,
                "error": "No segmentation result from Gemini"
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"[TryOnService] Segmentation error: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }


# 单例实例
tryon_service = TryOnService()
