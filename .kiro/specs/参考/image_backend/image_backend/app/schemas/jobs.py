from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal
from app.schemas.images import ImageB64

Platform = Literal["developer", "vertex"]

class JobRequest(BaseModel):
    mode_id: str
    platform: Optional[Platform] = Field(
        None, description="UI selected platform. Backend enforces routing rules."
    )

    model: Optional[str] = None
    prompt: Optional[str] = None

    image: Optional[ImageB64] = None
    mask: Optional[ImageB64] = None

    person_image: Optional[ImageB64] = None
    product_images: Optional[List[ImageB64]] = None

    params: Dict[str, Any] = Field(default_factory=dict)

class JobResponse(BaseModel):
    mode_id: str
    model: str
    text: Optional[str] = None
    images: List[ImageB64] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None
