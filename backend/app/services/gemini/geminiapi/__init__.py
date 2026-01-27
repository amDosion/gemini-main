"""
Gemini API 专用服务模块

这些服务只需要 API Key，使用 generateContent API。
所有服务通过 client_pool.get_client(api_key=xxx) 获取客户端。

服务列表:
- imagen_gemini_api: Gemini API 图像生成
- image_edit_gemini_api: Gemini API 图像编辑
- conversational_image_edit_service: 对话式图像编辑
"""

__all__ = [
    "imagen_gemini_api",
    "image_edit_gemini_api",
    "conversational_image_edit_service",
]
