"""
Vertex AI implementation for image editing.

This module provides backward compatibility by re-exporting VertexAIEditBase
as VertexAIImageEditor. New code should import from vertex_edit_base.py or
use the specific service files (inpainting_service.py, background_edit_service.py,
recontext_service.py, mask_edit_service.py).

Migration guide:
    # Old:
    from ..vertexai.image_edit_vertex_ai import VertexAIImageEditor
    editor = VertexAIImageEditor(project_id, location, credentials_json)

    # New (equivalent):
    from ..vertexai.vertex_edit_base import VertexAIEditBase
    editor = VertexAIEditBase(project_id, location, credentials_json)

    # New (recommended - use specific service):
    from ..vertexai.inpainting_service import InpaintingService
    editor = InpaintingService(project_id, location, credentials_json)
"""

from .vertex_edit_base import VertexAIEditBase, DEFAULT_EDIT_MODEL

# Backward compatibility alias
VertexAIImageEditor = VertexAIEditBase

__all__ = ['VertexAIImageEditor', 'DEFAULT_EDIT_MODEL']
