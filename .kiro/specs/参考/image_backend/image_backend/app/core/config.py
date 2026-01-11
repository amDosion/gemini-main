import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Vertex (ADC)
    project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    # Developer API key
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

settings = Settings()
