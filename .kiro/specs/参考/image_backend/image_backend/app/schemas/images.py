from pydantic import BaseModel, Field

class ImageB64(BaseModel):
    data_b64: str = Field(..., description="Base64 bytes (no data: prefix)")
    mime_type: str = Field(..., description="image/png | image/jpeg | image/webp")
