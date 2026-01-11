"""
Google (Gemini) Provider Service - Main Coordinator

This module coordinates all Gemini-related operations by delegating to specialized handlers.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Union, Type
import logging
from sqlalchemy.orm import Session

from ..base_provider import BaseProviderService
from ..model_capabilities import ModelConfig, build_model_config

from .sdk_initializer import SDKInitializer
from .chat_handler import ChatHandler
from .image_generator import ImageGenerator
from .image_edit_coordinator import ImageEditCoordinator
from .model_manager import ModelManager
from .file_handler import FileHandler
from .function_handler import FunctionHandler
from .schema_handler import SchemaHandler
from .token_handler import TokenHandler
from .official_sdk_adapter import OfficialSDKAdapter
from .expand_service import ExpandService
from .upscale_service import UpscaleService
from .segmentation_service import SegmentationService
from .tryon_service import TryOnService
from .pdf_extractor import PDFExtractorService

logger = logging.getLogger(__name__)


class GoogleService(BaseProviderService):
    """
    Google Gemini Provider Service - Main Coordinator.

    This service coordinates all Gemini operations by delegating to:
    - SDKInitializer: SDK initialization
    - ChatHandler: Chat operations
    - ImageGenerator: Image generation
    - ModelManager: Model listing
    - FileHandler: File upload/download operations
    - FunctionHandler: Function calling and tool integration
    - SchemaHandler: Structured JSON response handling
    - TokenHandler: Token counting and cost estimation
    - ExpandService: Image expansion/outpainting
    - UpscaleService: Image upscaling
    - SegmentationService: Image segmentation
    - TryOnService: Virtual try-on
    - PDFExtractor: PDF structured data extraction

    Official SDK: https://googleapis.github.io/python-genai/
    """
    
    def __init__(
        self, 
        api_key: str, 
        api_url: Optional[str] = None, 
        use_official_sdk: bool = False,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs
    ):
        """
        Initialize Google service coordinator.
        
        Args:
            api_key: Google API key for authentication
            api_url: Optional custom API URL
            use_official_sdk: Whether to use the official Google GenAI SDK compatibility layer
            user_id: Optional user ID for Vertex AI configuration lookup
            db: Optional database session for Vertex AI configuration lookup
            **kwargs: Additional parameters
        """
        super().__init__(api_key, api_url, **kwargs)
        
        self.user_id = user_id
        self.db = db
        self.use_official_sdk = use_official_sdk
        
        if use_official_sdk:
            # Initialize official SDK adapter
            self.official_adapter = OfficialSDKAdapter(
                api_key=api_key,
                use_vertex=kwargs.get('use_vertex', False),
                project=kwargs.get('project'),
                location=kwargs.get('location')
            )
            logger.info("[Google Service] Using Official SDK compatibility layer")
        else:
            # Initialize legacy SDK manager
            self.sdk_initializer = SDKInitializer(api_key)
            
            # Initialize handlers
            self.chat_handler = ChatHandler(self.sdk_initializer)
            # 使用 Gemini API 进行图像生成
            self.image_generator = ImageGenerator(
                api_key=api_key,
                user_id=user_id,
                db=db
            )
            # Initialize image edit coordinator
            self.image_edit_coordinator = ImageEditCoordinator(
                user_id=user_id,
                db=db
            )
            self.model_manager = ModelManager(api_key, api_url)
            
            # Initialize new handlers (P0 features)
            self.file_handler = FileHandler(self.sdk_initializer)
            self.function_handler = FunctionHandler(self.sdk_initializer)
            self.schema_handler = SchemaHandler(self.sdk_initializer)
            self.token_handler = TokenHandler(self.sdk_initializer)
            
            # Initialize specialized image services
            self.expand_service = ExpandService(self.sdk_initializer)
            self.upscale_service = UpscaleService(self.sdk_initializer)
            self.segmentation_service = SegmentationService(self.sdk_initializer)

            # Initialize PDF extraction service
            self.pdf_extractor = PDFExtractorService(self.sdk_initializer)

            # Initialize virtual try-on service
            self.tryon_service = TryOnService()

            logger.info("[Google Service] Using legacy SDK implementation")
    
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """Delegate to ChatHandler or Official SDK Adapter."""
        if self.use_official_sdk:
            return await self.official_adapter.generate_content(messages, model, **kwargs)
        else:
            return await self.chat_handler.chat(messages, model, **kwargs)
    
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        enable_search: bool = False,
        enable_thinking: bool = False,
        enable_code_execution: bool = False,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Delegate to ChatHandler or Official SDK Adapter."""
        if self.use_official_sdk:
            async for chunk in self.official_adapter.stream_generate_content(messages, model, **kwargs):
                yield chunk
        else:
            async for chunk in self.chat_handler.stream_chat(
                messages, model, enable_search, enable_thinking,
                enable_code_execution, enable_grounding, **kwargs
            ):
                yield chunk
    
    async def generate_image(
        self,
        prompt: str,
        model: str,  # 移除硬编码默认值，由前端传递
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Delegate to ImageGenerator.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use (must be provided by caller, no default)
            **kwargs: Additional parameters
        """
        logger.info(f"[Google Service] Delegating image generation to ImageGenerator: model={model}, prompt='{prompt[:50]}...'")
        logger.info(f"[Google Service] Additional parameters: {list(kwargs.keys())}")
        
        return await self.image_generator.generate_image(prompt, model, **kwargs)
    
    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Edit images using Google Imagen.
        
        Args:
            prompt: Text description of the desired edit
            model: Model to use for editing
            reference_images: Dictionary mapping reference image types to Base64-encoded images
                Required key: 'raw' (base image)
                Optional keys: 'mask', 'control', 'style', 'subject', 'content'
            **kwargs: Additional parameters (edit_mode, number_of_images, aspect_ratio, etc.)
        
        Returns:
            List of edited images with metadata
        
        Raises:
            NotSupportedError: If Gemini API mode is used (only Vertex AI supports editing)
        """
        logger.info(f"[Google Service] Delegating image editing to ImageEditCoordinator: model={model}, prompt='{prompt[:50]}...'")
        logger.info(f"[Google Service] Reference images: {list(reference_images.keys())}, additional parameters: {list(kwargs.keys())}")
        
        editor = self.image_edit_coordinator.get_editor()
        return await editor.edit_image(
            prompt=prompt,
            reference_images=reference_images,
            config=kwargs
        )
    
    async def get_available_models(self) -> List[ModelConfig]:
        """Delegate to ModelManager."""
        return await self.model_manager.get_available_models()
    
    def get_provider_name(self) -> str:
        """Get the name of this provider."""
        return "Google"
    
    async def generate_video(
        self, 
        prompt: str, 
        model: str = "veo-001", 
        **kwargs
    ) -> Dict[str, Any]:
        """Video generation not yet implemented."""
        raise NotImplementedError(
            "Video generation with Veo requires special API access. "
            "Please use the Vertex AI API or contact Google Cloud support."
        )
    
    # === File Operations (NEW) ===
    
    async def upload_file(
        self,
        file_path: str,
        display_name: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delegate to FileHandler."""
        return await self.file_handler.upload_file(file_path, display_name, mime_type)
    
    async def get_file_info(self, file_name: str) -> Dict[str, Any]:
        """Delegate to FileHandler."""
        return await self.file_handler.get_file_info(file_name)
    
    async def download_file(self, file_name: str, save_path: Optional[str] = None) -> bytes:
        """Delegate to FileHandler."""
        return await self.file_handler.download_file(file_name, save_path)
    
    async def delete_file(self, file_name: str) -> bool:
        """Delegate to FileHandler."""
        return await self.file_handler.delete_file(file_name)
    
    async def list_files(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """Delegate to FileHandler."""
        return await self.file_handler.list_files(page_size)
    
    # === Function Calling (NEW) ===
    
    def register_function(self, func, name: Optional[str] = None) -> str:
        """Delegate to FunctionHandler."""
        return self.function_handler.register_function(func, name)
    
    def create_tool_config(
        self,
        functions: List,
        mode: str = "AUTO",
        allowed_function_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Delegate to FunctionHandler."""
        from .function_handler import FunctionCallingMode
        mode_enum = FunctionCallingMode(mode)
        return self.function_handler.create_tool_config(functions, mode_enum, allowed_function_names)
    
    async def execute_function_call(self, function_call: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to FunctionHandler."""
        return await self.function_handler.execute_function_call(function_call)
    
    # === Structured Response (NEW) ===
    
    def create_json_schema_config(
        self,
        schema: Dict[str, Any],
        mime_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """Delegate to SchemaHandler."""
        return self.schema_handler.create_json_schema_config(schema, mime_type)
    
    def create_pydantic_schema_config(
        self,
        model_class,
        mime_type: str = 'application/json'
    ) -> Dict[str, Any]:
        """Delegate to SchemaHandler."""
        return self.schema_handler.create_pydantic_schema_config(model_class, mime_type)
    
    def parse_structured_response(
        self,
        response: Any,
        target_type: Optional[Type] = None
    ):
        """Delegate to SchemaHandler."""
        return self.schema_handler.parse_structured_response(response, target_type)
    
    # === Token Management (NEW) ===
    
    async def count_tokens(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str
    ):
        """Delegate to TokenHandler."""
        return await self.token_handler.count_tokens(content, model)
    
    async def compute_tokens(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ):
        """Delegate to TokenHandler."""
        return await self.token_handler.compute_tokens(content, model, tools, system_instruction)
    
    def estimate_cost(self, token_count, model: str, is_input: bool = True) -> float:
        """Delegate to TokenHandler."""
        return self.token_handler.estimate_cost(token_count, model, is_input)
    
    def get_model_pricing(self, model: str):
        """Delegate to TokenHandler."""
        return self.token_handler.get_model_pricing(model)
    
    def check_token_limit(self, token_count, model: str) -> Dict[str, Any]:
        """Delegate to TokenHandler."""
        if self.use_official_sdk:
            # Official SDK doesn't have token limit checking yet
            return {"within_limit": True, "limit": 1000000, "usage": token_count}
        else:
            return self.token_handler.check_token_limit(token_count, model)
    
    # === Deep Research Agent (NEW - Official SDK Only) ===
    
    async def create_deep_research(
        self,
        query: str,
        agent: str = 'deep-research-pro-preview-12-2025',
        background: bool = True
    ) -> Dict[str, Any]:
        """
        Create a Deep Research Agent interaction.
        
        Args:
            query: Research query
            agent: Agent name (default: Deep Research Agent)
            background: Whether to run in background mode
            
        Returns:
            Interaction result with ID and status
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        return await self.official_adapter.create_deep_research_interaction(
            query=query,
            agent=agent,
            background=background
        )
    
    async def get_research_status(self, interaction_id: str) -> Dict[str, Any]:
        """
        Get the status of a Deep Research interaction.
        
        Args:
            interaction_id: Interaction ID
            
        Returns:
            Interaction status and results
        """
        if not self.use_official_sdk:
            raise NotImplementedError(
                "Deep Research Agent is only available with the official SDK. "
                "Initialize GoogleService with use_official_sdk=True"
            )
        
        return await self.official_adapter.get_interaction_status(interaction_id)
    
    # === Image Expansion Service ===
    
    async def expand_image(
        self,
        image_path: str,
        expand_prompt: str,
        model: str,  # 移除硬编码默认值，由前端传递
        mode: str = "scale",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Expand image using outpainting.
        
        Args:
            image_path: Path to the image to expand
            expand_prompt: Description of what to add in expanded areas
            mode: Expansion mode ('scale', 'offset', 'ratio')
            model: Model to use for expansion (must be provided by caller, no default)
            **kwargs: Additional parameters
        
        Returns:
            List of expanded images
        """
        if self.use_official_sdk:
            raise NotImplementedError("Image expansion not yet implemented in official SDK adapter")
        
        prompt_log = f"expand_prompt='{expand_prompt[:30]}...'" if len(expand_prompt) > 30 else f"expand_prompt='{expand_prompt}'"
        logger.info(f"[Google Service] Delegating image expansion to ExpandService: model={model}, mode={mode}")
        logger.info(f"[Google Service] Expansion parameters: {prompt_log}, additional_params={list(kwargs.keys())}")

        return await self.expand_service.expand_image(image_path, expand_prompt, model, mode, **kwargs)
    
    # === Image Upscaling Service ===
    
    async def upscale_image(
        self,
        image_path: str,
        upscale_factor: str,  # 移除硬编码默认值，由前端传递
        model: str,  # 移除硬编码默认值，由前端传递
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Upscale image resolution by 2x or 4x.
        
        Args:
            image_path: Path to the image to upscale
            upscale_factor: Upscale factor ('x2' or 'x4') - must be provided by caller
            model: Model to use for upscaling (must be provided by caller, no default)
            **kwargs: Additional parameters
        
        Returns:
            List of upscaled images
        """
        if self.use_official_sdk:
            raise NotImplementedError("Image upscaling not yet implemented in official SDK adapter")
        
        logger.info(f"[Google Service] Delegating image upscaling to UpscaleService: factor={upscale_factor}, model={model}")
        logger.info(f"[Google Service] Additional parameters: {list(kwargs.keys())}")
        
        return await self.upscale_service.upscale_image(image_path, upscale_factor, model, **kwargs)
    
    # === Image Segmentation Service ===
    
    async def segment_image(
        self,
        image_path: str,
        model: str,  # 移除硬编码默认值，由前端传递
        prompt: Optional[str] = None,
        mask_mode: str = "MASK_MODE_FOREGROUND",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Segment objects in an image and create masks.
        
        Args:
            image_path: Path to the image to segment
            prompt: Optional text prompt for guided segmentation
            mask_mode: Segmentation mode
            model: Model to use for segmentation (must be provided by caller, no default)
            **kwargs: Additional parameters
        
        Returns:
            List of generated masks
        """
        if self.use_official_sdk:
            raise NotImplementedError("Image segmentation not yet implemented in official SDK adapter")
        
        prompt_log = f"prompt='{prompt[:30]}...'" if prompt and len(prompt) > 30 else f"prompt='{prompt}'"
        logger.info(f"[Google Service] Delegating image segmentation to SegmentationService: model={model}, mask_mode={mask_mode}")
        logger.info(f"[Google Service] Segmentation parameters: {prompt_log}, additional_params={list(kwargs.keys())}")

        return await self.segmentation_service.segment_image(image_path, model, prompt, mask_mode, **kwargs)

    # === PDF Extraction Service ===

    async def extract_pdf_data(
        self,
        pdf_bytes: bytes,
        template_type: str,
        model_id: str,
        additional_instructions: str = ""
    ) -> Dict[str, Any]:
        """
        Extract structured data from PDF using Gemini function calling.

        Args:
            pdf_bytes: PDF file content as bytes
            template_type: Template type ('invoice', 'form', 'receipt', 'contract', 'full-text')
            model_id: Model to use for extraction (required)
            additional_instructions: Optional additional extraction instructions

        Returns:
            Dictionary containing extracted structured data
        """
        if self.use_official_sdk:
            raise NotImplementedError("PDF extraction not yet implemented in official SDK adapter")

        logger.info(f"[Google Service] Delegating PDF extraction to PDFExtractorService: template={template_type}, model={model_id}")
        return await self.pdf_extractor.extract_structured_data(pdf_bytes, template_type, model_id, additional_instructions)

    def get_pdf_templates(self) -> List[Dict[str, str]]:
        """Delegate to PDFExtractorService."""
        return self.pdf_extractor.get_available_templates()

    # === Virtual Try-On Service ===

    def virtual_tryon(
        self,
        image_base64: str,
        mask_base64: Optional[str],
        prompt: str,
        edit_mode: str = "inpainting-insert",
        mask_mode: str = "foreground",
        dilation: float = 0.02,
        target_clothing: str = "upper body clothing"
    ):
        """
        Virtual try-on using image editing.

        Args:
            image_base64: Base64 encoded person image
            mask_base64: Base64 encoded mask image (optional)
            prompt: Description of clothing to try on
            edit_mode: Edit mode ('inpainting-insert', 'inpainting-remove')
            mask_mode: Mask mode ('foreground', 'background')
            dilation: Mask dilation factor
            target_clothing: Target clothing area

        Returns:
            TryOnResult with success status and result image
        """
        if self.use_official_sdk:
            raise NotImplementedError("Virtual try-on not yet implemented in official SDK adapter")

        logger.info(f"[Google Service] Delegating virtual try-on to TryOnService: mode={edit_mode}, prompt={prompt[:50]}...")
        return self.tryon_service.edit_with_mask(
            image_base64=image_base64,
            mask_base64=mask_base64,
            prompt=prompt,
            edit_mode=edit_mode,
            mask_mode=mask_mode,
            dilation=dilation,
            api_key=self.api_key,
            target_clothing=target_clothing
        )
